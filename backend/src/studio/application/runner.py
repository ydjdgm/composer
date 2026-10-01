import logging
import time
from collections.abc import Callable

from studio.domain.jobs import ClaimedJob, LeaseLost, StudioError
from studio.ports.providers import ExecutionContext, SongFixtureProvider
from studio.ports.queue import JobQueue

log = logging.getLogger("studio.worker")


def execute_job(job: ClaimedJob, queue: JobQueue, provider: SongFixtureProvider,
                validate: Callable[[ClaimedJob, Callable[[], bool]], dict]) -> None:
    started = time.monotonic()
    last_check = 0.0

    def cancelled() -> bool:
        nonlocal last_check
        if time.monotonic() - last_check >= 1:
            queue.checkpoint(job)
            last_check = time.monotonic()
        return False  # checkpoint raises LeaseLost after committing cancellation.

    try:
        queue.checkpoint(job, "running")
        if job.kind == "validate_upload":
            result = validate(job, cancelled)
        elif job.kind == "mock_song":
            result = provider.generate(job.input, ExecutionContext(
                str(job.id), job.input.get("seed"), lambda stage: queue.checkpoint(job, stage)))
        else:
            raise StudioError("unsupported_capability", "지원하지 않는 작업입니다.")
        queue.checkpoint(job, "postprocessing")
        queue.complete(job, result)
        log.info("job=%s project=%s kind=%s stage=completed seconds=%.2f",
                 job.id, job.project_id, job.kind, time.monotonic() - started)
    except LeaseLost:
        log.info("job=%s stage=stopped reason=lease_lost_or_cancelled", job.id)
    except StudioError as exc:
        queue.fail(job, exc.code, exc.message)
        log.warning("job=%s kind=%s category=%s", job.id, job.kind, exc.code)
    except Exception as exc:
        queue.fail(job, "provider_failure", "작업 처리 중 오류가 발생했습니다. 작업 ID와 로그를 확인하세요.")
        # Do not log uploaded content, DB parameters, credentials or local file paths.
        log.error("job=%s kind=%s category=%s", job.id, job.kind, type(exc).__name__)
