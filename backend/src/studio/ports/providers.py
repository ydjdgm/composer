from dataclasses import dataclass
from typing import Any, Callable, Protocol


@dataclass(frozen=True)
class ExecutionContext:
    job_id: str
    seed: int | None
    checkpoint: Callable[[str], None]


class SongFixtureProvider(Protocol):
    """Phase 1 workflow fixture, deliberately not a real composition provider."""

    def describe(self) -> dict[str, Any]: ...

    def generate(self, snapshot: dict[str, Any], context: ExecutionContext) -> dict[str, Any]: ...
