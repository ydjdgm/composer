from functools import lru_cache

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, Integer, MetaData,
    String, Table, Text, Uuid, create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB

from studio.settings import settings

# DDL lives in the immutable Alembic migration, not create_all at app startup.
metadata = MetaData()


def identity_columns():
    return [Column("id", Uuid, primary_key=True), Column("created_at", DateTime(timezone=True))]


projects = Table("projects", metadata, *identity_columns(),
    Column("title", String(160)), Column("brief", Text),
    Column("head_revision_id", Uuid), Column("updated_at", DateTime(timezone=True)))

assets = Table("assets", metadata, *identity_columns(),
    Column("project_id", Uuid), Column("kind", String(32)),
    Column("storage_key", Text), Column("checksum", String(64)),
    Column("byte_size", BigInteger), Column("media_type", String(80)),
    Column("extension", String(8)), Column("validation_state", String(16)),
    Column("audio_metadata", JSONB), Column("error", JSONB))

references = Table("reference_tracks", metadata, *identity_columns(),
    Column("project_id", Uuid), Column("asset_id", Uuid),
    Column("label", String(160)), Column("weights", JSONB), Column("version", Integer))

jobs = Table("generation_jobs", metadata, *identity_columns(),
    Column("project_id", Uuid), Column("kind", String(32)), Column("state", String(20)),
    Column("stage", String(32)), Column("progress", Float), Column("is_mock", Boolean),
    Column("input", JSONB), Column("base_revision_id", Uuid),
    Column("result_revision_id", Uuid), Column("needs_review", Boolean),
    Column("idempotency_key", String(128)), Column("request_hash", String(64)),
    Column("attempt_token", Uuid), Column("lease_expires_at", DateTime(timezone=True)),
    Column("cancel_requested_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)), Column("error", JSONB))

revisions = Table("song_revisions", metadata, *identity_columns(),
    Column("project_id", Uuid), Column("parent_revision_id", Uuid),
    Column("created_by_job_id", Uuid), Column("schema_version", Integer),
    Column("is_mock", Boolean), Column("package", JSONB))


@lru_cache
def engine():
    return create_engine(settings().database_url, pool_pre_ping=True,
                         connect_args={"connect_timeout": 5}, hide_parameters=True)
