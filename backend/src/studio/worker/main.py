import logging
import time
from uuid import UUID

from studio.adapters.database import assets, engine
from studio.adapters.fake import FakeSongProvider
from studio.adapters.media import MediaError, validate_audio
from studio.adapters.queue import PostgresJobQueue
from studio.adapters.repository import scoped
from studio.adapters.storage import LocalAssetStore
from studio.application.runner import execute_job
from studio.domain.jobs import StudioError
from studio.settings import settings


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = settings()
    queue = PostgresJobQueue(config.lease_seconds)
    store = LocalAssetStore(config.asset_root)
    provider = FakeSongProvider()

    def validate(job, cancelled):
        with engine().connect() as connection:
            asset = scoped(connection, assets, job.project_id, UUID(job.input["asset_id"]))
        try:
            return validate_audio(store.path(asset["storage_key"]), asset["extension"],
                ffmpeg=config.ffmpeg, ffprobe=config.ffprobe,
                max_duration=config.max_audio_seconds, timeout=config.media_timeout_seconds,
                cancelled=cancelled)
        except MediaError as exc:
            raise StudioError(exc.code, exc.message) from exc

    logging.info("worker=local concurrency=1 provider=fake-song adapter=1 model=none")
    try:
        while True:
            try:
                job = queue.claim()
                if job:
                    execute_job(job, queue, provider, validate)
                else:
                    time.sleep(config.worker_poll_seconds)
            except Exception as exc:
                logging.error("worker category=%s; retrying queue in 5 seconds", type(exc).__name__)
                time.sleep(5)
    except KeyboardInterrupt:
        logging.info("worker stopped; unfinished leases will expire")


if __name__ == "__main__":
    main()
