"""CLI entrypoint for ``python -m src.mcp``."""

from .server import main


if __name__ == "__main__":
    raise SystemExit(main())
