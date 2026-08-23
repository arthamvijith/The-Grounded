"""Allow ``python -m grounded`` to run the project CLI."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
