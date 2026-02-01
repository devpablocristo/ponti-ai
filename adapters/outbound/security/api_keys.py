import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _load_keys() -> set[str]:
    raw = os.getenv("AI_API_KEYS", "").strip()
    if not raw:
        return set()
    return {key.strip() for key in raw.split(",") if key.strip()}


def is_valid_api_key(api_key: str) -> bool:
    keys = _load_keys()
    if not keys:
        return False
    return api_key in keys
