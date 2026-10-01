from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import insert, select, update

from studio.adapters.database import assets, engine, jobs, projects, revisions
from studio.adapters.repository import get_project, reject_validation_asset
from studio.domain.jobs import ACTIVE, ClaimedJob, LeaseLost, StudioError, utcnow


class PostgresJobQueue:
    def __init__(self, lease_seconds: int):
        self.lease_seconds = lease_seconds

    def claim(self) -> ClaimedJob | None:
        with engine().begin() as connection:
            now = utcnow()
            expired = connection.execute(select(jobs).where(jobs.c.state.in_(ACTIVE),
                jobs.c.lease_expires_at < now).with_for_update(skip_locked=True)).mappings().all()
            for row in expired:
                cancelled = row["cancel_requested_at"] is not None
                state = "cancelled" if cancelled else "failed"
                error = {"code": "cancelled" if cancelled else "worker_lost",
                         "message": "작업이 취소되었습니다." if cancelled else "작업 처리기 연결이 끊겼습니다. 다시 요청하세요."}
                connection.execute(update(jobs).where(jobs.c.id == row["id"])
                    .values(state=state, stage=state, error=error, updated_at=now, lease_expires_at=None))
                reject_validation_asset(connection, row, error)
            row = connection.execute(select(jobs).where(jobs.c.state == "queued")
                .order_by(jobs.c.created_at, jobs.c.id).limit(1)
                .with_for_update(skip_locked=True)).mappings().first()
            if not row:
                return None
            token = uuid4()
            connection.execute(update(jobs).where(jobs.c.id == row["id"]).values(
                state="preparing", stage="preparing", attempt_token=token, updated_at=now,
                lease_expires_at=now + timedelta(seconds=self.lease_seconds)))
            return ClaimedJob(row["id"], row["project_id"], row["kind"], token, row["input"])

    def owned(self, connection, job: ClaimedJob):
        row = connection.execute(select(jobs).where(jobs.c.id == job.id)
                                 .with_for_update()).mappings().one()
        if (row["state"] not in ACTIVE or row["attempt_token"] != job.token
                or row["lease_expires_at"] is None or row["lease_expires_at"] <= utcnow()):
            raise LeaseLost()
        return row

    def checkpoint(self, job: ClaimedJob, stage: str | None = None):
        cancelled = False
        with engine().begin() as connection:
            row = self.owned(connection, job)
            now = utcnow()
            if row["cancel_requested_at"]:
                cancelled = True
                error = {"code": "cancelled", "message": "작업이 취소되었습니다."}
                connection.execute(update(jobs).where(jobs.c.id == job.id).values(
                    state="cancelled", stage="cancelled", error=error, updated_at=now, lease_expires_at=None))
                reject_validation_asset(connection, row, error)
            else:
                values = {"updated_at": now, "lease_expires_at": now + timedelta(seconds=self.lease_seconds)}
                if stage:
                    if stage not in ACTIVE:
                        raise ValueError("Invalid active stage")
                    values.update(state=stage, stage=stage)
                connection.execute(update(jobs).where(jobs.c.id == job.id).values(**values))
        if cancelled:
            raise LeaseLost()

    def complete(self, job: ClaimedJob, result: dict):
        with engine().begin() as connection:
            # Project first: matches enqueue lock order and prevents head overwrite.
            project = get_project(connection, job.project_id, lock=True)
            row = self.owned(connection, job)
            if row["cancel_requested_at"]:
                raise StudioError("cancelled", "작업이 취소되었습니다.")
            values = dict(state="completed", stage="completed", progress=1.0,
                          lease_expires_at=None, updated_at=utcnow())
            if job.kind == "validate_upload":
                connection.execute(update(assets).where(assets.c.id == UUID(job.input["asset_id"]),
                    assets.c.project_id == job.project_id, assets.c.validation_state == "pending")
                    .values(validation_state="ready", audio_metadata=result, error=None))
            else:
                revision_id = uuid4()
                result["identity"] = {"schema_version": 1, "project_id": str(job.project_id),
                    "revision_id": str(revision_id), "parent_revision_id":
                    str(row["base_revision_id"]) if row["base_revision_id"] else None,
                    "title": job.input["title"]}
                connection.execute(insert(revisions).values(id=revision_id, project_id=job.project_id,
                    parent_revision_id=row["base_revision_id"], created_by_job_id=job.id,
                    schema_version=1, is_mock=True, package=result, created_at=utcnow()))
                needs_review = project["head_revision_id"] != row["base_revision_id"]
                values.update(result_revision_id=revision_id, needs_review=needs_review)
                if not needs_review:
                    connection.execute(update(projects).where(projects.c.id == job.project_id)
                        .values(head_revision_id=revision_id, updated_at=utcnow()))
            connection.execute(update(jobs).where(jobs.c.id == job.id).values(**values))

    def fail(self, job: ClaimedJob, code: str, message: str):
        try:
            with engine().begin() as connection:
                row = self.owned(connection, job)
                cancelled = row["cancel_requested_at"] is not None or code == "cancelled"
                state = "cancelled" if cancelled else "failed"
                error = {"code": "cancelled" if cancelled else code,
                         "message": "작업이 취소되었습니다." if cancelled else message}
                connection.execute(update(jobs).where(jobs.c.id == job.id).values(
                    state=state, stage=state, error=error, lease_expires_at=None, updated_at=utcnow()))
                reject_validation_asset(connection, row, error)
        except LeaseLost:
            return
