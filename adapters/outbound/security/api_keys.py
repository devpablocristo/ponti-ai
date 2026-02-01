import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _load_keys() -> set[str]:
    raw = os.getenv("AI_SERVICE_KEYS", "").strip()
    if not raw:
        return set()
    return {key.strip() for key in raw.split(",") if key.strip()}


def is_valid_service_key(service_key: str) -> bool:
    keys = _load_keys()
    if not keys:
        return False
    return service_key in keys
