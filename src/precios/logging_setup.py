import logging

from rich.console import Console
from rich.logging import RichHandler

_console = Console()


def get_console() -> Console:
    return _console


def get_logger(name: str = "precios") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = RichHandler(
            console=_console, rich_tracebacks=True, show_time=True, show_path=False
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
