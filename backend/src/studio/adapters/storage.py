"""Local immutable asset storage; only server-generated keys are accepted."""

import hashlib
from pathlib import Path, PurePosixPath

from studio.ports.storage import StorageError, UploadSource


class LocalAssetStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        parts = PurePosixPath(key)
        if (
            not key
            or "\\" in key
            or ":" in key
            or "\x00" in key
            or parts.is_absolute()
            or any(part in {".", "..", ""} for part in key.split("/"))
        ):
            raise StorageError("invalid_asset_key", "Invalid asset key.")
        path = (self.root / Path(*parts.parts)).resolve()
        if path == self.root or not path.is_relative_to(self.root):
            raise StorageError("invalid_asset_key", "Invalid asset key.")
        return path

    async def write_upload(
        self, file: UploadSource, key: str, max_bytes: int
    ) -> tuple[int, str]:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        path = self.path(key)
        created = False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Re-resolve after mkdir; never overwrite an existing asset.
            path = self.path(key)
            with path.open("xb") as target:
                created = True
                total = 0
                digest = hashlib.sha256()
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise StorageError("file_too_large", "Upload exceeds the file size limit.")
                    target.write(chunk)
                    digest.update(chunk)
                if total == 0:
                    raise StorageError("empty_upload", "The uploaded file is empty.")
            return total, digest.hexdigest()
        except BaseException as exc:
            if created:
                path.unlink(missing_ok=True)
            if isinstance(exc, FileExistsError):
                raise StorageError("asset_exists", "The asset already exists.") from exc
            if isinstance(exc, OSError):
                raise StorageError("storage_unavailable", "Asset storage is unavailable.") from exc
            raise

    def delete(self, key: str) -> None:
        try:
            self.path(key).unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError("storage_unavailable", "Could not remove the asset.") from exc
