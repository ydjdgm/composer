"""Explicit local orphan cleanup; never runs at API/worker startup."""
import argparse
import time
from uuid import UUID

from sqlalchemy import select

from studio.adapters.database import assets, engine
from studio.adapters.storage import LocalAssetStore
from studio.settings import settings


def main():
    parser = argparse.ArgumentParser(description="List unregistered uploads older than 48 hours.")
    parser.add_argument("--delete", action="store_true", help="Delete listed orphan files. Stop API uploads first.")
    args = parser.parse_args()
    store = LocalAssetStore(settings().asset_root)
    cutoff = time.time() - 48 * 3600
    # Only the documented UUID/UUID.ext layout; never recurse through arbitrary paths.
    with engine().connect() as connection:
        for folder in store.root.iterdir():
            if folder.is_symlink() or not folder.is_dir():
                continue
            try:
                UUID(folder.name)
            except ValueError:
                continue
            for file in folder.iterdir():
                if file.is_symlink() or not file.is_file() or file.suffix not in {".wav", ".mp3", ".flac"}:
                    continue
                try:
                    UUID(file.stem)
                except ValueError:
                    continue
                key = f"{folder.name}/{file.name}"
                path = store.path(key)
                if path.stat().st_mtime >= cutoff:
                    continue
                registered = connection.scalar(select(assets.c.id).where(assets.c.storage_key == key))
                if registered is None:
                    print(f"orphan {key}")
                    if args.delete:
                        store.delete(key)


if __name__ == "__main__":
    main()
