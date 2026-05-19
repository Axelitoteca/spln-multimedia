"""Alias para `python -m precios.run` (delega en cli.main)."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
