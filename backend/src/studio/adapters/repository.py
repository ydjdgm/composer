"""Transactional persistence operations. All project-scoped lookups are constrained."""
import base64
import hashlib
import json
from datetime import datetime
from typing import Any, Callable
from uuid import UUID, uuid4

from sqlalchemy import and_, func, insert, or_, select, update

from studio.adapters.database import assets, engine, jobs, projects, references, revisions
from studio.domain.jobs import StudioError, TERMINAL, utcnow

JOB_PUBLIC = ("id", "project_id", "kind", "state", "stage", "progress", "is_mock",
              "base_revision_id", "result_revision_id", "needs_review", "cancel_requested_at",
              "created_at", "updated_at", "error")
ASSET_PUBLIC = ("id", "project_id", "kind", "checksum", "byte_size", "media_type",
                "validation_state", "audio_metadata", "error", "created_at")
DEFAULT_WEIGHTS = {key: 0.0 for key in (
    "rhythm", "energy", "atmosphere", "instrumentation", "harmony", "production_texture")}


def public_job(row) -> dict:
    return {key: row[key] for key in JOB_PUBLIC}


def public_asset(row) -> dict:
    return {key: row[key] for key in ASSET_PUBLIC}


def get_project(connection, project_id: UUID, *, lock=False):
    query = select(projects).where(projects.c.id == project_id)
    row = connection.execute(query.with_for_update() if lock else query).mappings().first()
    if not row:
        raise StudioError("not_found", "프로젝트를 찾을 수 없습니다.", 404)
    return row


def scoped(connection, table, project_id: UUID, item_id: UUID, *, lock=False):
    query = select(table).where(table.c.id == item_id, table.c.project_id == project_id)
    row = connection.execute(query.with_for_update() if lock else query).mappings().first()
    if not row:
        raise StudioError("not_found", "항목을 찾을 수 없습니다.", 404)
    return row


def page(connection, table, cursor: str | None, limit: int, *, project_id=None,
         serialize: Callable = dict, active_only=False):
    query = select(table)
    if project_id is not None:
        get_project(connection, project_id)
        query = query.where(table.c.project_id == project_id)
    if active_only:
        query = query.where(table.c.state.not_in(TERMINAL))
    if cursor:
        try:
            created, identifier = json.loads(base64.urlsafe_b64decode(cursor).decode("utf-8"))
            if not isinstance(created, str) or not isinstance(identifier, str):
                raise ValueError()
            stamp, item_id = datetime.fromisoformat(created), UUID(identifier)
            if stamp.tzinfo is None:
                raise ValueError()
        except (ValueError, TypeError, UnicodeError, KeyError) as exc:
            raise StudioError("invalid_cursor", "목록 커서가 잘못되었습니다.") from exc
        query = query.where(or_(table.c.created_at < stamp,
            and_(table.c.created_at == stamp, table.c.id < item_id)))
    rows = connection.execute(query.order_by(table.c.created_at.desc(), table.c.id.desc())
                              .limit(limit + 1)).mappings().all()
    visible = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = visible[-1]
        next_cursor = base64.urlsafe_b64encode(json.dumps(
            [last["created_at"].isoformat(), str(last["id"])]).encode()).decode()
    return {"items": [serialize(row) for row in visible], "next_cursor": next_cursor}


def create_project(title: str, brief: str):
    with engine().begin() as connection:
        return dict(connection.execute(insert(projects).values(
            id=uuid4(), title=title, brief=brief, created_at=utcnow(), updated_at=utcnow()
        ).returning(projects)).mappings().one())


def new_job(project_id, kind, snapshot, **extra):
    now = utcnow()
    return dict(id=uuid4(), project_id=project_id, kind=kind, input=snapshot,
                state="queued", stage="queued", is_mock=kind == "mock_song", progress=None,
                created_at=now, updated_at=now, needs_review=False, **extra)


def reference_view(connection, row):
    asset = scoped(connection, assets, row["project_id"], row["asset_id"])
    return {**dict(row), "validation_state": asset["validation_state"],
            "audio_metadata": asset["audio_metadata"], "error": asset["error"],
            "asset": public_asset(asset)}


def upload_preflight(project_id: UUID, max_references: int):
    with engine().connect() as connection:
        get_project(connection, project_id)
        count = connection.scalar(select(func.count()).select_from(references)
                                  .where(references.c.project_id == project_id))
        if count >= max_references:
            raise StudioError("reference_limit", "프로젝트의 참조곡 개수 제한에 도달했습니다.", 409)


def register_upload(project_id, asset_id, key, size, checksum, extension, media_type, label,
                    max_references):
    with engine().begin() as connection:
        get_project(connection, project_id, lock=True)
        count = connection.scalar(select(func.count()).select_from(references)
                                  .where(references.c.project_id == project_id))
        if count >= max_references:
            raise StudioError("reference_limit", "프로젝트의 참조곡 개수 제한에 도달했습니다.", 409)
        asset = connection.execute(insert(assets).values(
            id=asset_id, project_id=project_id, kind="reference", storage_key=key,
            checksum=checksum, byte_size=size, media_type=media_type, extension=extension,
            validation_state="pending", created_at=utcnow()
        ).returning(assets)).mappings().one()
        reference = connection.execute(insert(references).values(
            id=uuid4(), project_id=project_id, asset_id=asset_id, label=label,
            weights=DEFAULT_WEIGHTS, version=1, created_at=utcnow()
        ).returning(references)).mappings().one()
        job = connection.execute(insert(jobs).values(**new_job(project_id, "validate_upload",
            {"asset_id": str(asset_id)})).returning(jobs)).mappings().one()
        return {"reference": reference_view(connection, reference), "asset": public_asset(asset),
                "validation_job": public_job(job)}


def edit_reference(project_id, reference_id, expected_version, changes):
    with engine().begin() as connection:
        # Same lock order as generation snapshot: project, then reference.
        get_project(connection, project_id, lock=True)
        row = scoped(connection, references, project_id, reference_id, lock=True)
        if row["version"] != expected_version:
            raise StudioError("version_conflict", "참조곡이 변경되었습니다. 새로고침 후 다시 저장하세요.", 409)
        result = connection.execute(update(references).where(references.c.id == reference_id)
            .values(**changes, version=expected_version + 1).returning(references)).mappings().one()
        return reference_view(connection, result)


def enqueue_generation(project_id: UUID, body: dict[str, Any], key: str):
    request_hash = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"))
                                  .encode()).hexdigest()
    with engine().begin() as connection:
        project = get_project(connection, project_id, lock=True)
        existing = connection.execute(select(jobs).where(jobs.c.project_id == project_id,
            jobs.c.kind == "mock_song", jobs.c.idempotency_key == key)).mappings().first()
        if existing:
            if existing["request_hash"] != request_hash:
                raise StudioError("idempotency_conflict", "같은 요청 키에 다른 내용이 전달되었습니다.", 409)
            return public_job(existing)
        base_id = UUID(body["base_revision_id"]) if body["base_revision_id"] else None
        if base_id != project["head_revision_id"]:
            raise StudioError("revision_conflict", "프로젝트의 최신 revision을 다시 불러오세요.", 409)
        reference_snapshot = []
        for identifier in body["reference_ids"]:
            row = scoped(connection, references, project_id, UUID(identifier))
            asset = scoped(connection, assets, project_id, row["asset_id"])
            if asset["validation_state"] != "ready":
                raise StudioError("reference_not_ready", "검증 완료된 참조곡만 사용할 수 있습니다.", 409)
            reference_snapshot.append({"reference_id": str(row["id"]), "version": row["version"],
                "asset_id": str(asset["id"]), "checksum": asset["checksum"],
                "weights": row["weights"], "analysis_id": None, "analysis_status": "unsupported"})
        snapshot = {"title": project["title"], "brief": body["brief"],
                    "seed": body["seed"], "references": reference_snapshot,
                    "provider_id": "fake-song", "adapter_version": "1"}
        row = connection.execute(insert(jobs).values(**new_job(project_id, "mock_song", snapshot,
            base_revision_id=base_id, idempotency_key=key, request_hash=request_hash))
            .returning(jobs)).mappings().one()
        return public_job(row)


def reject_validation_asset(connection, job, error):
    if job["kind"] == "validate_upload":
        connection.execute(update(assets).where(assets.c.id == UUID(job["input"]["asset_id"]),
            assets.c.project_id == job["project_id"], assets.c.validation_state == "pending")
            .values(validation_state="rejected", error=error))


def cancel_job(project_id, job_id):
    with engine().begin() as connection:
        row = scoped(connection, jobs, project_id, job_id, lock=True)
        if row["state"] == "cancelled":
            return public_job(row)
        if row["state"] in TERMINAL:
            raise StudioError("invalid_state", "이미 종료된 작업은 취소할 수 없습니다.", 409)
        changes = {"cancel_requested_at": row["cancel_requested_at"] or utcnow(), "updated_at": utcnow()}
        if row["state"] == "queued":
            changes.update(state="cancelled", stage="cancelled")
            reject_validation_asset(connection, row, {"code": "cancelled", "message": "검증이 취소되었습니다."})
        result = connection.execute(update(jobs).where(jobs.c.id == job_id).values(**changes)
                                    .returning(jobs)).mappings().one()
        return public_job(result)
