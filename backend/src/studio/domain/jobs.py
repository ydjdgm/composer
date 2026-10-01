from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

TERMINAL = frozenset({"completed", "failed", "cancelled"})
ACTIVE = ("preparing", "running", "postprocessing")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ClaimedJob:
    id: UUID
    project_id: UUID
    kind: str
    token: UUID
    input: dict[str, Any]


class StudioError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class LeaseLost(Exception):
    """The worker no longer owns this attempt; no publication is allowed."""
