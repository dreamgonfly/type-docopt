from type_docopt import docopt

from pytest import raises


def test_custom_types():
    class CustomType:
        def __init__(self, number):
            self.number = int(number)
            if self.number >= 10:
                raise ValueError

        def __eq__(self, other):
            return self.number == other.number

    assert docopt(
        "Usage: prog [--foo=<foo>]\n"
        "Options: -f --foo=<foo>  Lorem ipsum dolor [type: CustomType]",
        argv="--foo=1",
        types={"CustomType": CustomType},
    ) == {"--foo": CustomType("1")}

    assert docopt(
        "Usage: prog [--foo=<foo>]\n"
        "Options: -f --foo=<foo>  Lorem ipsum dolor [type: CustomType]",
        argv="",
        types={"CustomType": CustomType},
    ) == {"--foo": None}

    with raises(ValueError):
        docopt(
            "Usage: prog [--foo=<foo>]\n"
            "Options: -f --foo=<foo>  Lorem ipsum dolor [type: CustomType]",
            argv="--foo=20",
            types={"CustomType": CustomType},
        )

    assert docopt(
        "Usage: prog [--foo=<foo>]\n"
        "Options: -f --foo=<foo>  Lorem ipsum dolor [type: CustomType] [default: 5]",
        "",
        types={"CustomType": CustomType},
    ) == {"--foo": CustomType("5")}


def test_choices():
    assert docopt(
        "Usage: prog [--foo=<foo>]\n" "Options: -f --foo=<foo>  Lorem ipsum dolor [choices: A B C]",
        "--foo=A",
    ) == {"--foo": "A"}

    with raises(ValueError):
        docopt(
            "Usage: prog [--foo=<foo>]\n"
            "Options: -f --foo=<foo>  Lorem ipsum dolor [choices: A B C]",
            "--foo=D",
        )
