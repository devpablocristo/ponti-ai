import json
import logging
from typing import Any


def get_logger(name: str = "ponti-ai") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        logger.propagate = False
        return logger
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def log_event(event: str, payload: dict[str, Any]) -> None:
    logger = get_logger()
    message = {"event": event, **payload}
    logger.info(json.dumps(message))
