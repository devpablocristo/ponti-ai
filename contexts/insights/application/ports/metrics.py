from typing import Protocol


class MetricsPort(Protocol):
    def inc_counter(self, name: str, value: int = 1) -> None:
        ...
