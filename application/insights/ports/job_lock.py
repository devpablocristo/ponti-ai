from typing import Protocol


class JobLockPort(Protocol):
    def try_lock(self, key: int) -> bool:
        ...

    def release(self, key: int) -> None:
        ...
