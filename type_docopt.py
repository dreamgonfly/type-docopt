"""Type-Docopt is a Pythonic command-line interface parser with type conversion.

Based on docopt (https://github.com/docopt/docopt).
"""
import sys
import re
import inspect


from typing import Any, List, Optional, Tuple, Type, Union, Dict, Callable

__all__ = ["docopt"]

BASIC_TYPE_MAP = {
    "int": int,
    "float": float,
    "complex": complex,
    "str": str,
}


class DocoptLanguageError(Exception):

    """Error in construction of usage-message by developer."""


class DocoptExit(SystemExit):

    """Exit in case user invoked program with incorrect arguments."""

    usage = ""

    def __init__(
        self, message: str = "", collected: List["Pattern"] = None, left: List["Pattern"] = None,
    ) -> None:
        self.collected = collected if collected is not None else []
        self.left = left if left is not None else []
        SystemExit.__init__(self, (message + "\n" + self.usage).strip())


class Pattern:
    def __init__(
        self, name: Optional[str], value: Optional[Union[List[str], str, int]] = None
    ) -> None:
        self._name, self.value = name, value

    @property
    def name(self) -> Optional[str]:
        return self._name

    def __eq__(self, other: Any) -> bool:
        return repr(self) == repr(other)

    def __hash__(self) -> int:
        return hash(repr(self))


def transform(pattern: "BranchPattern") -> "Either":
    """Expand pattern into an (almost) equivalent one, but with single Either.

    Example: ((-a | -b) (-c | -d)) => (-a -c | -a -d | -b -c | -b -d)
    Quirks: [-a] => (-a), (-a...) => (-a -a)

    """
    result = []
    groups = [[pattern]]
    while groups:
        children = groups.pop(0)
        parents = [Required, NotRequired, OptionsShortcut, Either, OneOrMore]
        if any(t in map(type, children) for t in parents):
            child = [c for c in children if type(c) in parents][0]
            children.remove(child)
            if type(child) is Either:
                for c in child.children:
                    groups.append([c] + children)
            elif type(child) is OneOrMore:
                groups.append(child.children * 2 + children)
            else:
                groups.append(child.children + children)
        else:
            result.append(children)
    return Either(*[Required(*e) for e in result])


TSingleMatch = Tuple[Union[int, None], Union["LeafPattern", None]]


class LeafPattern(Pattern):

    """Leaf/terminal node of a pattern tree."""

    def __repr__(self) -> str:
        return "%s(%r, %r)" % (self.__class__.__name__, self.name, self.value)

    def single_match(self, left: List["LeafPattern"]) -> TSingleMatch:
        raise NotImplementedError  # pragma: no cover

    def flat(self, *types) -> List["LeafPattern"]:
        return [self] if not types or type(self) in types else []

    def match(
        self, left: List["LeafPattern"], collected: List["Pattern"] = None
    ) -> Tuple[bool, List["LeafPattern"], List["Pattern"]]:
        collected = [] if collected is None else collected
        increment: Optional[Any] = None
        pos, match = self.single_match(left)
        if match is None or pos is None:
            return False, left, collected
        left_ = left[:pos] + left[(pos + 1) :]
        same_name = [a for a in collected if a.name == self.name]
        if type(self.value) == int and len(same_name) > 0:
            if isinstance(same_name[0].value, int):
                same_name[0].value += 1
            return True, left_, collected
        if type(self.value) == int and not same_name:
            match.value = 1
            return True, left_, collected + [match]
        if same_name and type(self.value) == list:
            if type(match.value) == str:
                increment = [match.value]
            if same_name[0].value is not None and increment is not None:
                if isinstance(same_name[0].value, type(increment)):
                    same_name[0].value += increment
            return True, left_, collected
        elif not same_name and type(self.value) == list:
            if isinstance(match.value, str):
                match.value = [match.value]
            return True, left_, collected + [match]
        return True, left_, collected + [match]


class BranchPattern(Pattern):

    """Branch/inner node of a pattern tree."""

    def __init__(self, *children) -> None:
        self.children = list(children)

    def match(self, left: List["Pattern"], collected: List["Pattern"] = None) -> Any:
        raise NotImplementedError  # pragma: no cover

    def fix(self) -> "BranchPattern":
        self.fix_identities()
        self.fix_repeating_arguments()
        return self

    def fix_identities(self, uniq: Optional[Any] = None) -> None:
        """Make pattern-tree tips point to same object if they are equal."""
        flattened = self.flat()
        uniq = list(set(flattened)) if uniq is None else uniq
        for i, child in enumerate(self.children):
            if not hasattr(child, "children"):
                assert child in uniq
                self.children[i] = uniq[uniq.index(child)]
            else:
                child.fix_identities(uniq)
        return None

    def fix_repeating_arguments(self) -> "BranchPattern":
        """Fix elements that should accumulate/increment values."""
        either = [list(child.children) for child in transform(self).children]
        for case in either:
            for e in [child for child in case if case.count(child) > 1]:
                if type(e) is Argument or type(e) is Option and e.argcount:
                    if e.value is None:
                        e.value = []
                    elif type(e.value) is not list:
                        e.value = e.value.split()
                if type(e) is Command or type(e) is Option and e.argcount == 0:
                    e.value = 0
        return self

    def __repr__(self) -> str:
        return "%s(%s)" % (self.__class__.__name__, ", ".join(repr(a) for a in self.children),)

    def flat(self, *types) -> Any:
        if type(self) in types:
            return [self]
        return sum([child.flat(*types) for child in self.children], [])


class Argument(LeafPattern):
    def single_match(self, left: List[LeafPattern]) -> TSingleMatch:
        for n, pattern in enumerate(left):
            if type(pattern) is Argument:
                return n, Argument(self.name, pattern.value)
        return None, None


class Command(Argument):
    def __init__(self, name: Union[str, None], value: bool = False) -> None:
        self._name, self.value = name, value

    def single_match(self, left: List[LeafPattern]) -> TSingleMatch:
        for n, pattern in enumerate(left):
            if type(pattern) is Argument:
                if pattern.value == self.name:
                    return n, Command(self.name, True)
                else:
                    break
        return None, None


class Option(LeafPattern):
    def __init__(
        self,
        short: Optional[str] = None,
        longer: Optional[str] = None,
        argcount: int = 0,
        value: Union[List[str], str, int, None] = False,
        type_name: Optional[str] = None,
        choices: Optional[List[str]] = None,
    ) -> None:
        assert argcount in (0, 1)
        self.short, self.longer, self.argcount = short, longer, argcount
        self.value = None if value is False and argcount else value
        self.type_name = type_name
        self.choices = choices

    @classmethod
    def parse(class_, option_description: str) -> "Option":
        short, longer, argcount, value = None, None, 0, False
        options, _, description = option_description.strip().partition("  ")
        options = options.replace(",", " ").replace("=", " ")
        for s in options.split():
            if s.startswith("--"):
                longer = s
            elif s.startswith("-"):
                short = s
            else:
                argcount = 1
        if argcount:
            matched = re.findall(r"\[default: (.*?)\]", description, flags=re.I)
            value = matched[0] if matched else None

        type_matched = re.findall(r"\[type: (.*?)\]", description, flags=re.I)
        type_name = type_matched[0] if type_matched else None

        choices_matched = re.findall(r"\[choices: (.*?)\]", description, flags=re.I)
        if choices_matched:
            choices_value = choices_matched[0]
            choices = [choice.strip() for choice in choices_value.split(" ")]
        else:
            choices = None

        return class_(short, longer, argcount, value, type_name, choices)

    def single_match(self, left: List[LeafPattern]) -> TSingleMatch:
        for n, pattern in enumerate(left):
            if self.name == pattern.name:
                return n, pattern
        return None, None

    @property
    def name(self) -> Optional[str]:
        return self.longer or self.short

    def __repr__(self) -> str:
        return "Option(%r, %r, %r, %r, %r, %r)" % (
            self.short,
            self.longer,
            self.argcount,
            self.value,
            self.type_name,
            self.choices,
        )


class Required(BranchPattern):
    def match(self, left: List["Pattern"], collected: List["Pattern"] = None) -> Any:
        collected = [] if collected is None else collected
        original_collected = collected
        original_left = left
        for pattern in self.children:
            matched, left, collected = pattern.match(left, collected)
            if not matched:
                return False, original_left, original_collected
        return True, left, collected


class NotRequired(BranchPattern):
    def match(self, left: List["Pattern"], collected: List["Pattern"] = None) -> Any:
        collected = [] if collected is None else collected
        for pattern in self.children:
            _, left, collected = pattern.match(left, collected)
        return True, left, collected


class OptionsShortcut(NotRequired):

    """Marker/placeholder for [options] shortcut."""


class OneOrMore(BranchPattern):
    def match(self, left: List[Pattern], collected: List[Pattern] = None) -> Any:
        assert len(self.children) == 1
        collected = [] if collected is None else collected
        original_collected = collected
        original_left = left
        last_left = None
        matched = True
        times = 0
        while matched:
            matched, left, collected = self.children[0].match(left, collected)
            times += 1 if matched else 0
            if last_left == left:
                break
            last_left = left
        if times >= 1:
            return True, left, collected
        return False, original_left, original_collected


class Either(BranchPattern):
    def match(self, left: List["Pattern"], collected: List["Pattern"] = None) -> Any:
        collected = [] if collected is None else collected
        outcomes = []
        for pattern in self.children:
            matched, _, _ = outcome = pattern.match(left, collected)
            if matched:
                outcomes.append(outcome)
        if outcomes:
            return min(outcomes, key=lambda outcome: len(outcome[1]))
        return False, left, collected


class Tokens(list):
    def __init__(
        self,
        source: Union[List[str], str],
        error: Union[Type[DocoptExit], Type[DocoptLanguageError]] = DocoptExit,
    ) -> None:
        if isinstance(source, list):
            self += source
        else:
            self += source.split()
        self.error = error

    @staticmethod
    def from_pattern(source: str) -> "Tokens":
        source = re.sub(r"([\[\]\(\)\|]|\.\.\.)", r" \1 ", source)
        fragments = [s for s in re.split(r"\s+|(\S*<.*?>)", source) if s]
        return Tokens(fragments, error=DocoptLanguageError)

    def move(self) -> Optional[str]:
        return self.pop(0) if len(self) else None

    def current(self) -> Optional[str]:
        return self[0] if len(self) else None


def parse_longer(tokens: Tokens, options: List[Option], argv: bool = False) -> List[Pattern]:
    """longer ::= '--' chars [ ( ' ' | '=' ) chars ] ;"""
    current_token = tokens.move()
    if current_token is None or not current_token.startswith("--"):
        raise tokens.error(
            f"parse_longer got what appears to be an invalid token: {current_token}"
        )  # pragma: no cover
    longer, maybe_eq, maybe_value = current_token.partition("=")
    if maybe_eq == maybe_value == "":
        value = None
    else:
        value = maybe_value
    similar = [o for o in options if o.longer and longer == o.longer]
    start_collision = (
        len([o for o in options if o.longer and longer in o.longer and o.longer.startswith(longer)])
        > 1
    )
    if argv and not len(similar) and not start_collision:
        similar = [
            o for o in options if o.longer and longer in o.longer and o.longer.startswith(longer)
        ]
    if len(similar) > 1:
        raise tokens.error(f"{longer} is not a unique prefix: {similar}?")  # pragma: no cover
    elif len(similar) < 1:
        argcount = 1 if maybe_eq == "=" else 0
        o = Option(None, longer, argcount)
        options.append(o)
        if tokens.error is DocoptExit:
            o = Option(None, longer, argcount, value if argcount else True)
    else:
        o = Option(
            similar[0].short,
            similar[0].longer,
            similar[0].argcount,
            similar[0].value,
            similar[0].type_name,
            similar[0].choices,
        )
        if o.argcount == 0:
            if value is not None:
                raise tokens.error("%s must not have an argument" % o.longer)
        else:
            if value is None:
                if tokens.current() in [None, "--"]:
                    raise tokens.error("%s requires argument" % o.longer)
                value = tokens.move()
        if tokens.error is DocoptExit:
            o.value = value if value is not None else True
    return [o]


def parse_shorts(tokens: Tokens, options: List[Option]) -> List[Pattern]:
    """shorts ::= '-' ( chars )* [ [ ' ' ] chars ] ;"""
    token = tokens.move()
    if token is None or not token.startswith("-") or token.startswith("--"):
        raise ValueError(
            f"parse_shorts got what appears to be an invalid token: {token}"
        )  # pragma: no cover
    left = token.lstrip("-")
    parsed: List[Pattern] = []
    while left != "":
        short, left = "-" + left[0], left[1:]
        transformations: Dict[Union[None, str], Callable[[str], str]] = {None: lambda x: x}
        # try identity, lowercase, uppercase, iff such resolves uniquely (ie if upper and lowercase are not both defined)
        similar: List[Option] = []
        de_abbreviated = False
        for transform_name, transform in transformations.items():
            transformed = list(set([transform(o.short) for o in options if o.short]))
            no_collisions = len(
                [o for o in options if o.short and transformed.count(transform(o.short)) == 1]
            )  # == len(transformed)
            if no_collisions:
                similar = [o for o in options if o.short and transform(o.short) == transform(short)]
                if similar:
                    if transform_name:
                        print(f"NB: Corrected {short} to {similar[0].short} via {transform_name}")
                    break
        if len(similar) > 1:
            raise tokens.error("%s is specified ambiguously %d times" % (short, len(similar)))
        elif len(similar) < 1:
            o = Option(short, None, 0)
            options.append(o)
            if tokens.error is DocoptExit:
                o = Option(short, None, 0, True)
        else:
            if de_abbreviated:
                option_short_value = None
            else:
                option_short_value = transform(short)
            o = Option(
                option_short_value,
                similar[0].longer,
                similar[0].argcount,
                similar[0].value,
                similar[0].type_name,
                similar[0].choices,
            )
            value = None
            current_token = tokens.current()
            if o.argcount != 0:
                if left == "":
                    if current_token is None or current_token == "--":
                        raise tokens.error("%s requires argument" % short)
                    else:
                        value = tokens.move()
                else:
                    value = left
                    left = ""
            if tokens.error is DocoptExit:
                o.value = value if value is not None else True
        parsed.append(o)
    return parsed


def parse_pattern(source: str, options: List[Option]) -> Required:
    tokens = Tokens.from_pattern(source)
    result = parse_expr(tokens, options)
    if tokens.current() is not None:
        raise tokens.error("unexpected ending: %r" % " ".join(tokens))
    return Required(*result)


def parse_expr(tokens: Tokens, options: List[Option]) -> List[Pattern]:
    """expr ::= seq ( '|' seq )* ;"""
    result: List[Pattern] = []
    seq_0: List[Pattern] = parse_seq(tokens, options)
    if tokens.current() != "|":
        return seq_0
    if len(seq_0) > 1:
        result.append(Required(*seq_0))
    else:
        result += seq_0
    while tokens.current() == "|":
        tokens.move()
        seq_1 = parse_seq(tokens, options)
        if len(seq_1) > 1:
            result += [Required(*seq_1)]
        else:
            result += seq_1
    return [Either(*result)]


def parse_seq(tokens: Tokens, options: List[Option]) -> List[Pattern]:
    """seq ::= ( atom [ '...' ] )* ;"""
    result: List[Pattern] = []
    while tokens.current() not in [None, "]", ")", "|"]:
        atom = parse_atom(tokens, options)
        if tokens.current() == "...":
            atom = [OneOrMore(*atom)]
            tokens.move()
        result += atom
    return result


def parse_atom(tokens: Tokens, options: List[Option]) -> List[Pattern]:
    """atom ::= '(' expr ')' | '[' expr ']' | 'options'
             | longer | shorts | argument | command ;
    """
    token = tokens.current()
    if not token:
        return [Command(tokens.move())]  # pragma: no cover
    elif token in "([":
        tokens.move()
        matching = {"(": ")", "[": "]"}[token]
        pattern = {"(": Required, "[": NotRequired}[token]
        matched_pattern = pattern(*parse_expr(tokens, options))
        if tokens.move() != matching:
            raise tokens.error("unmatched '%s'" % token)
        return [matched_pattern]
    elif token == "options":
        tokens.move()
        return [OptionsShortcut()]
    elif token.startswith("--") and token != "--":
        return parse_longer(tokens, options)
    elif token.startswith("-") and token not in ("-", "--"):
        return parse_shorts(tokens, options)
    elif token.startswith("<") and token.endswith(">") or token.isupper():
        return [Argument(tokens.move())]
    else:
        return [Command(tokens.move())]


def parse_argv(
    tokens: Tokens, options: List[Option], options_first: bool = False,
) -> List[Pattern]:
    """Parse command-line argument vector.

    If options_first:
        argv ::= [ longer | shorts ]* [ argument ]* [ '--' [ argument ]* ] ;
    else:
        argv ::= [ longer | shorts | argument ]* [ '--' [ argument ]* ] ;

    """

    def isanumber(x):
        try:
            float(x)
            return True
        except ValueError:
            return False

    parsed: List[Pattern] = []
    current_token = tokens.current()
    while current_token is not None:
        if current_token == "--":
            return parsed + [Argument(None, v) for v in tokens]
        elif current_token.startswith("--"):
            parsed += parse_longer(tokens, options, argv=True)
        elif (
            current_token.startswith("-") and current_token != "-" and not isanumber(current_token)
        ):
            parsed += parse_shorts(tokens, options)
        elif options_first:
            return parsed + [Argument(None, v) for v in tokens]
        else:
            parsed.append(Argument(None, tokens.move()))
        current_token = tokens.current()
    return parsed


def parse_description(docstring: str) -> List[Option]:
    defaults = []
    for s in parse_section("options:", docstring):
        options_literal, _, s = s.partition(":")
        if " " in options_literal:
            _, _, options_literal = options_literal.partition(" ")
        assert options_literal.lower().strip() == "options"
        split = re.split(r"\n[ \t]*(-\S+?)", "\n" + s)[1:]
        split = [s1 + s2 for s1, s2 in zip(split[::2], split[1::2])]
        for s in split:
            if s.startswith("-"):
                arg, _, description = s.partition("  ")
                flag, _, var = arg.replace("=", " ").partition(" ")
                option = Option.parse(s)
                defaults.append(option)
    return defaults


def parse_section(name: str, source: str) -> List[str]:
    pattern = re.compile(
        "^([^\n]*" + name + "[^\n]*\n?(?:[ \t].*?(?:\n|$))*)", re.IGNORECASE | re.MULTILINE,
    )
    r = [s.strip() for s in pattern.findall(source) if s.strip().lower() != name.lower()]
    return r


def formal_usage(section: str) -> str:
    _, _, section = section.partition(":")  # drop "usage:"
    pu = section.split()
    return "( " + " ".join(") | (" if s == pu[0] else s for s in pu[1:]) + " )"


def extras(help_message: bool, version: None, options: List[Pattern], docstring: str) -> None:
    if help_message and any(
        (o.name in ("-h", "--help")) and o.value for o in options if isinstance(o, Option)
    ):
        print(docstring.strip("\n"))
        sys.exit()
    if version and any(o.name == "--version" and o.value for o in options if isinstance(o, Option)):
        print(version)
        sys.exit()


class ParsedOptions(dict):
    def __repr__(self):
        return "{%s}" % ",\n ".join("%r: %r" % i for i in sorted(self.items()))

    def __getattr__(self, name: str) -> Optional[Union[str, bool]]:
        return self.get(name) or {
            name: self.get(k)
            for k in self.keys()
            if name in [k.lstrip("-"), k.lstrip("<").rstrip(">")]
        }.get(name)


def convert_type(o: Pattern, types: Optional[Dict[str, Type]]):
    if not isinstance(o, Option):
        return o.value

    if o.value is None:
        return o.value

    if o.choices is not None:
        if o.value.lower() not in [choice.lower() for choice in o.choices]:
            raise ValueError(f"{o.value} is not in {o.choices}.")

    if o.type_name is not None:
        if types is not None:
            type_map = dict(**BASIC_TYPE_MAP, **types)
        else:
            type_map = BASIC_TYPE_MAP
        if o.type_name not in type_map:
            raise ValueError(f"{o.type_name} type is not provided.")

        type_ = type_map[o.type_name]
        o.value = type_(o.value)

    return o.value


def docopt(
    docstring: Optional[str] = None,
    argv: Optional[Union[List[str], str]] = None,
    help_message: bool = True,
    version: Any = None,
    options_first: bool = False,
    types: Dict[str, Type] = None,
) -> ParsedOptions:
    """Parse `argv` based on command-line interface described in `doc`.

    `docopt` creates your command-line interface based on its
    description that you pass as `docstring`. Such description can contain
    --options, <positional-argument>, commands, which could be
    [optional], (required), (mutually | exclusive) or repeated...

    Parameters
    ----------
    docstring : str (default: first __doc__ in parent scope)
        Description of your command-line interface.
    argv : list of str, optional
        Argument vector to be parsed. sys.argv[1:] is used if not
        provided.
    help_message : bool (default: True)
        Set to False to disable automatic help on -h or --help
        options.
    version : any object
        If passed, the object will be printed if --version is in
        `argv`.
    options_first : bool (default: False)
        Set to True to require options precede positional arguments,
        i.e. to forbid options and positional arguments intermix.
    types : dict
        Provide user-defined types to parse type information in
        docstring.

    Returns
    -------
    arguments: dict-like
        A dictionary, where keys are names of command-line elements
        such as e.g. "--verbose" and "<path>", and values are the
        parsed values of those elements. Also supports dot acccess.

    Example
    -------
    >>> from type_docopt import docopt
    >>> doc = '''
    ... Usage:
    ...   my_program tcp <host> <port> [--timeout=<seconds>]
    ...   my_program serial <port> [--baud=<n>] [--timeout=<seconds>]
    ...   my_program (-h | --help | --version)
    ...
    ... Options:
    ...   -h, --help  Show this screen and exit.
    ...   --baud=<n>  Baudrate [default: 9600] [type: int]
    ...   --timeout=<seconds>  Timeout seconds [type: float]
    ... '''
    >>> argv = ['tcp', '127.0.0.1', '80', '--timeout', '30']
    >>> docopt(doc, argv)
    {'--baud': 9600,
     '--help': False,
     '--timeout': 30.0,
     '--version': False,
     '<host>': '127.0.0.1',
     '<port>': '80',
     'serial': False,
     'tcp': True}

    """
    argv = sys.argv[1:] if argv is None else argv
    frame = inspect.currentframe()
    doc_parent_frame = frame.f_back
    if not docstring:  # go look for one, if none exists, raise Exception
        while not docstring and doc_parent_frame:
            docstring = doc_parent_frame.f_locals.get("__doc__")
            if not docstring:
                doc_parent_frame = doc_parent_frame.f_back
        if not docstring:
            raise DocoptLanguageError(
                "Either __doc__ must be defined in the scope of a parent or passed as the first argument."
            )
    usage_sections = parse_section("usage:", docstring)
    if len(usage_sections) == 0:
        raise DocoptLanguageError(
            '"usage:" section (case-insensitive) not found. Perhaps missing indentation?'
        )
    if len(usage_sections) > 1:
        raise DocoptLanguageError('More than one "usage:" (case-insensitive).')
    options_pattern = re.compile(r"\n\s*?options:", re.IGNORECASE)
    if options_pattern.search(usage_sections[0]):
        raise DocoptExit(
            "Warning: options (case-insensitive) was found in usage."
            "Use a blank line between each section.."
        )
    DocoptExit.usage = usage_sections[0]
    options = parse_description(docstring)
    pattern = parse_pattern(formal_usage(DocoptExit.usage), options)
    pattern_options = set(pattern.flat(Option))
    for options_shortcut in pattern.flat(OptionsShortcut):
        doc_options = parse_description(docstring)
        options_shortcut.children = [opt for opt in doc_options if opt not in pattern_options]
    parsed_arg_vector = parse_argv(Tokens(argv), list(options), options_first)
    extras(help_message, version, parsed_arg_vector, docstring)
    matched, left, collected = pattern.fix().match(parsed_arg_vector)
    if matched and left == []:
        output_obj = ParsedOptions(
            (a.name, convert_type(a, types)) for a in (pattern.flat() + collected)
        )
        return output_obj
    if left:
        raise DocoptExit(f"Warning: found unmatched (duplicate?) arguments {left}")
    raise DocoptExit(collected=collected, left=left)
