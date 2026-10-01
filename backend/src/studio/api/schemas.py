from datetime import datetime
from typing import Annotated, Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class ProjectCreate(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    brief: str = Field(default="", max_length=8000)


class ProjectView(ProjectCreate):
    id: UUID
    head_revision_id: UUID | None
    created_at: datetime
    updated_at: datetime


Weight = Annotated[float, Field(ge=0, le=1)]


class Weights(StrictModel):
    rhythm: Weight = 0
    energy: Weight = 0
    atmosphere: Weight = 0
    instrumentation: Weight = 0
    harmony: Weight = 0
    production_texture: Weight = 0


class ReferencePatch(StrictModel):
    expected_version: int = Field(ge=1)
    label: str | None = Field(default=None, min_length=1, max_length=160)
    weights: Weights | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if self.label is None and self.weights is None:
            raise ValueError("At least one change is required")
        return self


class ErrorInfo(BaseModel):
    code: str
    message: str


class AudioMetadata(BaseModel):
    duration_seconds: float
    sample_rate: int
    channels: int
    frame_count: int
    format: str


class AssetView(BaseModel):
    id: UUID
    project_id: UUID
    kind: str
    checksum: str
    byte_size: int
    media_type: str
    validation_state: Literal["pending", "ready", "rejected"]
    audio_metadata: AudioMetadata | None
    error: ErrorInfo | None
    created_at: datetime


class ReferenceView(BaseModel):
    id: UUID
    project_id: UUID
    asset_id: UUID
    label: str
    weights: Weights
    version: int
    created_at: datetime
    validation_state: Literal["pending", "ready", "rejected"]
    audio_metadata: AudioMetadata | None
    error: ErrorInfo | None
    asset: AssetView


class Brief(StrictModel):
    prompt: str = Field(min_length=1, max_length=8000)
    duration_seconds: int = Field(default=120, ge=1, le=600)
    language: str = Field(default="ko", min_length=2, max_length=32)
    genre: str | None = Field(default=None, max_length=120)


class GenerateRequest(StrictModel):
    kind: Literal["mock_song"] = "mock_song"
    base_revision_id: UUID | None = None
    reference_ids: list[UUID] = Field(default_factory=list, max_length=100)
    brief: Brief
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)

    @model_validator(mode="after")
    def unique_references(self):
        if len(set(self.reference_ids)) != len(self.reference_ids):
            raise ValueError("reference_ids must be unique")
        return self


class JobView(BaseModel):
    id: UUID
    project_id: UUID
    kind: Literal["mock_song", "validate_upload"]
    state: Literal["queued", "preparing", "running", "postprocessing", "completed", "failed", "cancelled"]
    stage: str
    progress: float | None
    is_mock: bool
    base_revision_id: UUID | None
    result_revision_id: UUID | None
    needs_review: bool
    cancel_requested_at: datetime | None
    created_at: datetime
    updated_at: datetime
    error: ErrorInfo | None


class UploadView(BaseModel):
    reference: ReferenceView
    asset: AssetView
    validation_job: JobView


class RevisionView(BaseModel):
    id: UUID
    project_id: UUID
    parent_revision_id: UUID | None
    created_by_job_id: UUID
    schema_version: int
    is_mock: bool
    created_at: datetime


class PackageIdentity(BaseModel):
    schema_version: Literal[1]
    project_id: UUID
    revision_id: UUID
    parent_revision_id: UUID | None
    title: str


class SongPackageView(BaseModel):
    identity: PackageIdentity
    brief: Brief
    reference_snapshot: list[dict[str, Any]]
    timing: dict[str, Any]
    tonality: dict[str, Any]
    sections: list[dict[str, Any]]
    lyrics: list[dict[str, Any]]
    composition: dict[str, Any]
    performances: list[dict[str, Any]]
    tracks: list[dict[str, Any]]
    mix: dict[str, Any]
    provenance: dict[str, Any]


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None
