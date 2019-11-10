from setuptools import setup

from type_docopt import __version__


setup(
    name='type-docopt',
    version=__version__,
    author='Yongrae Jo',
    author_email='dreamgonfly@gmail.com',
    description='Pythonic argument parser, with type validation',
    license='MIT',
    keywords='option arguments parsing optparse argparse getopt',
    url='http://docopt.org',
    py_modules=['type_docopt'],
    long_description=open('README.rst').read(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Topic :: Utilities',
        'Programming Language :: Python :: 2.5',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'License :: OSI Approved :: MIT License',
    ],
)
