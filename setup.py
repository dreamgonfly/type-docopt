import sys
from setuptools import setup
from setuptools.command.test import test as TestCommand

__version__ = "0.8.2"


class PyTestCommand(TestCommand):
    """Command to run unit tests"""

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run(self):
        import pytest

        rcode = pytest.main(self.test_args)
        sys.exit(rcode)


setup(
    name="type-docopt",
    version=__version__,
    description="Pythonic argument parser, with type description.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/dreamgonfly/type-docopt",
    author="Yongrae Jo",
    author_email="dreamgonfly@gmail.com",
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Utilities",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
    ],
    keywords="arguments parser argparse optparse getopt",
    py_modules=["type_docopt"],
    tests_require=["pytest"],
    cmdclass={"test": PyTestCommand},
)
