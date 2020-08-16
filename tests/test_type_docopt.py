from __future__ import with_statement

from type_docopt import (
    docopt,
    DocoptExit,
    DocoptLanguageError,
    Option,
    Argument,
    Command,
    AnyOptions,
    Required,
    Optional,
    Either,
    OneOrMore,
    parse_argv,
    parse_pattern,  # parse_defaults,
    printable_usage,
    formal_usage,
    TokenStream,
)
from pytest import raises


def test_types():
    doc = """Usage: prog [options]\n
Options:\n  -d --data=<data>    Input data [type: float]"""
    a = docopt(doc, "--data=0.1")
    assert a == {"--data": 0.1}
    doc = """Usage: prog [--data=<data>]\n
Options:\n  -d --data=<data>    Input data [default: 10] [type: int]
"""
    a = docopt(doc, "")
    assert a == {"--data": 10}
    doc = """Usage: prog [--data=<data>]\n
    Options:\n  -d --data=<data>    Input data [default: 10] [type: int]
    """
    a = docopt(doc, "--data=30")
    assert a == {"--data": 30}


def test_user_defined_types():
    doc = """Usage: prog [--data=<data>]\n
                     Options:\n  -d --data=<data>    Input data [type: Foo]
                  """

    class Foo:
        def __init__(self, number):
            self.number = int(number)
            assert self.number < 10

        def __eq__(self, other):
            return self.number == other.number

    a = docopt(doc, "--data=1", types={"Foo": Foo})
    assert a == {"--data": Foo("1")}

    with raises(AssertionError):
        docopt(doc, "--data=20", types={"Foo": Foo})

    doc = """Usage: prog [--data=<data>]\n
                         Options:\n  -d --data=<data>    Input data [type: Foo] [default: 5]
                      """
    a = docopt(doc, "", types={"Foo": Foo})
    assert a == {"--data": Foo("5")}

    doc = """Usage: prog [options]\n
    Options:\n  -d --data <data>  Input data [type: Foo]
    """
    a = docopt(doc, "", types={"Foo": Foo})
    assert a == {"--data": None}


def test_choices():
    doc = """Usage: prog [--data=<data>]\n
                 Options:\n  -d --data=<data>    Input data [choices: A B C]
              """
    a = docopt(doc, "--data=A")
    assert a == {"--data": "A"}
    doc = """Usage: prog [--data=<data>]\n
                     Options:\n  -d --data=<data>    Input data [choices: A B C] [default: C]
                  """
    a = docopt(doc, "")
    assert a == {"--data": "C"}

    doc = """Usage: prog [--data=<data>]\n
             Options:\n  -d --data=<data>    Input data [choices: A B C]
          """
    with raises(AssertionError):
        docopt(doc, "--data=D")


# https://github.com/docopt/docopt/issues/259
def test_blank_line_between_options():
    doc = """Usage: prog [options]

Options:
  -d --data=<data>    Input data [default: 10] [type: int]

  -i --input=<input>    Input [default: 0.1] [type: float]
"""
    a = docopt(doc, "")
    assert a == {"--data": 10, "--input": 0.1}
