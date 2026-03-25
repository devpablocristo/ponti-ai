# Delega a core_ai.logging para logging estructurado.
from typing import Any

from core_ai.logging import get_logger as _core_get_logger


def get_logger(name: str = "ponti-ai") -> Any:
    return _core_get_logger(name)


def log_event(event: str, payload: dict[str, Any]) -> None:
    logger = _core_get_logger("ponti-ai")
    logger.info(event, extra=payload)
