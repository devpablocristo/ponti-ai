import json
import logging
from typing import Any


def get_logger(name: str = "ai-copilot") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def log_event(event: str, payload: dict[str, Any]) -> None:
    logger = get_logger()
    message = {"event": event, **payload}
    logger.info(json.dumps(message))
