import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure structured console logging for the application.

    Args:
        level: String logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR').
    """
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
