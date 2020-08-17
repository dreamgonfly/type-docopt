"""Usage:
  quick_example.py tcp <host> <port> [--timeout=<seconds>]
  quick_example.py serial <port> [--baud=<n>] [--timeout=<seconds>]
  quick_example.py -h | --help | --version

Options:
  --baud=<n>  Baudrate [default: 9600] [type: int]
  --timeout=<seconds>  Timeout seconds [type: float]
"""
from type_docopt import docopt


if __name__ == "__main__":
    arguments = docopt(__doc__, version="0.1.1rc")
    print(arguments)
