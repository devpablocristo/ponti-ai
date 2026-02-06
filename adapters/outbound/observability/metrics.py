import threading
from collections import defaultdict
from typing import DefaultDict


_lock = threading.Lock()
_counters: DefaultDict[str, int] = defaultdict(int)
_timers_ms: DefaultDict[str, list[int]] = defaultdict(list)


def inc_counter(name: str, value: int = 1) -> None:
    with _lock:
        _counters[name] += value


def observe_ms(name: str, value_ms: int) -> None:
    with _lock:
        _timers_ms[name].append(value_ms)


def snapshot() -> dict[str, dict[str, float]]:
    with _lock:
        counters = {k: float(v) for k, v in _counters.items()}
        timers = {}
        for key, values in _timers_ms.items():
            if not values:
                continue
            timers[key] = {
                "count": float(len(values)),
                "avg_ms": float(sum(values) / len(values)),
                "max_ms": float(max(values)),
            }
    return {"counters": counters, "timers": timers}
