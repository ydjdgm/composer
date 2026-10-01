import logging
from pathlib import PurePosixPath
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, Header, Query, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from starlette.responses import FileResponse

from studio.adapters import repository as repo
from studio.adapters.database import assets, engine, jobs, projects, references, revisions
from studio.adapters.fake import FakeSongProvider
from studio.adapters.storage import LocalAssetStore
from studio.api.schemas import (
    AssetView, GenerateRequest, JobView, Page, ProjectCreate, ProjectView,
    ReferencePatch, ReferenceView, RevisionView, SongPackageView, UploadView,
)
from studio.domain.jobs import StudioError
from studio.ports.storage import StorageError
from studio.settings import settings

router = APIRouter(prefix="/api/v1")
Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(max_length=512)]


@router.post("/projects", status_code=201, response_model=ProjectView)
def create_project(body: ProjectCreate):
    return repo.create_project(body.title, body.brief)


@router.get("/projects", response_model=Page[ProjectView])
def list_projects(cursor: Cursor = None, limit: Limit = 50):
    with engine().connect() as connection:
        return repo.page(connection, projects, cursor, limit)


@router.get("/projects/{project_id}", response_model=ProjectView)
def project(project_id: UUID):
    with engine().connect() as connection:
        return dict(repo.get_project(connection, project_id))


@router.post("/projects/{project_id}/references", status_code=202, response_model=UploadView)
async def upload_reference(project_id: UUID, file: Annotated[UploadFile, File()],
                           label: Annotated[str | None, Form(max_length=160)] = None):
    config = settings()
    store = LocalAssetStore(config.asset_root)
    extension = PurePosixPath((file.filename or "").replace("\\", "/")).suffix.lower()
    formats = {".wav": ("audio/wav", {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"}),
               ".mp3": ("audio/mpeg", {"audio/mpeg", "audio/mp3"}),
               ".flac": ("audio/flac", {"audio/flac", "audio/x-flac"})}
    if extension not in formats or file.content_type not in formats[extension][1]:
        await file.close()
        raise StudioError("unsupported_media", "WAV, MP3, FLAC 오디오만 업로드할 수 있습니다.", 415)
    asset_id = uuid4()
    key = f"{project_id}/{asset_id}{extension}"
    written = False
    try:
        await run_in_threadpool(repo.upload_preflight, project_id, config.max_references)
        size, checksum = await store.write_upload(file, key, config.max_upload_bytes)
        written = True
        filename = PurePosixPath((file.filename or "참조곡").replace("\\", "/")).name
        return await run_in_threadpool(repo.register_upload, project_id, asset_id, key, size,
            checksum, extension, formats[extension][0], (label or filename).strip()[:160] or "참조곡",
            config.max_references)
    except StudioError:
        if written:
            try:
                store.delete(key)
            except StorageError:
                logging.getLogger("studio.api").error("asset=%s cleanup_failed", asset_id)
        raise
    except BaseException:
        # A disconnected DB commit may have succeeded. Never delete a potentially
        # referenced file; explicit orphan maintenance handles unregistered files.
        if written:
            logging.getLogger("studio.api").warning("asset=%s registration_outcome_uncertain", asset_id)
        raise
    finally:
        await file.close()


@router.get("/projects/{project_id}/references", response_model=Page[ReferenceView])
def list_references(project_id: UUID, cursor: Cursor = None, limit: Limit = 50):
    with engine().connect() as connection:
        return repo.page(connection, references, cursor, limit, project_id=project_id,
                         serialize=lambda row: repo.reference_view(connection, row))


@router.patch("/projects/{project_id}/references/{reference_id}", response_model=ReferenceView)
def patch_reference(project_id: UUID, reference_id: UUID, body: ReferencePatch):
    changes = body.model_dump(exclude={"expected_version"}, exclude_none=True)
    return repo.edit_reference(project_id, reference_id, body.expected_version, changes)


@router.get("/projects/{project_id}/assets/{asset_id}", response_model=AssetView)
def asset_metadata(project_id: UUID, asset_id: UUID):
    with engine().connect() as connection:
        return repo.public_asset(repo.scoped(connection, assets, project_id, asset_id))


@router.get("/projects/{project_id}/assets/{asset_id}/content")
def asset_content(project_id: UUID, asset_id: UUID):
    with engine().connect() as connection:
        asset = repo.scoped(connection, assets, project_id, asset_id)
    if asset["validation_state"] != "ready":
        raise StudioError("asset_not_ready", "검증 완료되지 않은 파일입니다.", 409)
    path = LocalAssetStore(settings().asset_root).path(asset["storage_key"])
    if not path.is_file():
        raise StudioError("asset_unavailable", "저장된 파일을 사용할 수 없습니다.", 404)
    return FileResponse(path, media_type=asset["media_type"], filename=f"{asset_id}{asset['extension']}",
                        headers={"X-Content-Type-Options": "nosniff"})


@router.post("/projects/{project_id}/generate", status_code=202, response_model=JobView)
def generate(project_id: UUID, body: GenerateRequest, response: Response,
             idempotency_key: Annotated[str, Header(min_length=1, max_length=128)]):
    if not idempotency_key.strip():
        raise StudioError("invalid_key", "요청 키가 비어 있습니다.")
    result = repo.enqueue_generation(project_id, body.model_dump(mode="json"), idempotency_key)
    response.headers["Location"] = f"/api/v1/projects/{project_id}/jobs/{result['id']}"
    return result


@router.get("/projects/{project_id}/jobs", response_model=Page[JobView])
def list_jobs(project_id: UUID, cursor: Cursor = None, limit: Limit = 50, active_only: bool = False):
    with engine().connect() as connection:
        return repo.page(connection, jobs, cursor, limit, project_id=project_id,
                         serialize=repo.public_job, active_only=active_only)


@router.get("/projects/{project_id}/jobs/{job_id}", response_model=JobView)
def get_job(project_id: UUID, job_id: UUID):
    with engine().connect() as connection:
        return repo.public_job(repo.scoped(connection, jobs, project_id, job_id))


@router.post("/projects/{project_id}/jobs/{job_id}/cancel", status_code=202, response_model=JobView)
def cancel_job(project_id: UUID, job_id: UUID, response: Response):
    result = repo.cancel_job(project_id, job_id)
    if result["state"] == "cancelled":
        response.status_code = 200
    return result


@router.get("/projects/{project_id}/revisions", response_model=Page[RevisionView])
def list_revisions(project_id: UUID, cursor: Cursor = None, limit: Limit = 50):
    with engine().connect() as connection:
        return repo.page(connection, revisions, cursor, limit, project_id=project_id,
                         serialize=lambda row: {k: v for k, v in row.items() if k != "package"})


@router.get("/projects/{project_id}/revisions/{revision_id}", response_model=SongPackageView)
def get_revision(project_id: UUID, revision_id: UUID):
    with engine().connect() as connection:
        return repo.scoped(connection, revisions, project_id, revision_id)["package"]


@router.get("/providers")
def providers():
    return {"items": [FakeSongProvider().describe()], "next_cursor": None}
