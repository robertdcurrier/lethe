"""Module entry point: enables `python -m lethe`."""
import sys

from lethe.cli import main


if __name__ == "__main__":
    sys.exit(main())
