"""Opaque asset keys keep storage details out of application contracts."""

from pathlib import Path
from typing import Protocol


class StorageError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class UploadSource(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


class AssetStore(Protocol):
    def path(self, key: str) -> Path: ...

    async def write_upload(
        self, file: UploadSource, key: str, max_bytes: int
    ) -> tuple[int, str]: ...

    def delete(self, key: str) -> None: ...
