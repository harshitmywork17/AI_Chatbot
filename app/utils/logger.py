"""Central logging configuration. Import get_logger(__name__) everywhere else."""

import logging

from app.core.config import get_settings

_CONFIGURED = False


def _configure_root_logger() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=get_settings().log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger, configuring the root logger on first use."""
    _configure_root_logger()
    return logging.getLogger(name)
