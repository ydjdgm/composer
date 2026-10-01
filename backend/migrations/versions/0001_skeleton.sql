CREATE TABLE projects (
    id uuid PRIMARY KEY, title varchar(160) NOT NULL, brief text NOT NULL DEFAULT '',
    head_revision_id uuid, created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE assets (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    kind varchar(32) NOT NULL, storage_key text NOT NULL UNIQUE,
    checksum varchar(64) NOT NULL, byte_size bigint NOT NULL CHECK (byte_size > 0),
    media_type varchar(80) NOT NULL, extension varchar(8) NOT NULL,
    validation_state varchar(16) NOT NULL CHECK (validation_state IN ('pending','ready','rejected')),
    audio_metadata jsonb, error jsonb, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id, id)
);
CREATE TABLE reference_tracks (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    asset_id uuid NOT NULL UNIQUE, label varchar(160) NOT NULL,
    weights jsonb NOT NULL, version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (project_id, asset_id) REFERENCES assets(project_id,id)
);
CREATE TABLE generation_jobs (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    kind varchar(32) NOT NULL CHECK (kind IN ('validate_upload','mock_song')),
    state varchar(20) NOT NULL CHECK (state IN ('queued','preparing','running','postprocessing','completed','failed','cancelled')),
    stage varchar(32) NOT NULL, progress double precision CHECK (progress BETWEEN 0 AND 1),
    is_mock boolean NOT NULL, input jsonb NOT NULL,
    base_revision_id uuid, result_revision_id uuid, needs_review boolean NOT NULL DEFAULT false,
    idempotency_key varchar(128), request_hash varchar(64), attempt_token uuid,
    lease_expires_at timestamptz, cancel_requested_at timestamptz,
    error jsonb, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id, kind, idempotency_key), UNIQUE(project_id, id)
);
CREATE TABLE song_revisions (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id), parent_revision_id uuid,
    created_by_job_id uuid NOT NULL UNIQUE, schema_version integer NOT NULL CHECK (schema_version = 1),
    is_mock boolean NOT NULL, package jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,id),
    FOREIGN KEY(project_id,parent_revision_id) REFERENCES song_revisions(project_id,id),
    FOREIGN KEY(project_id,created_by_job_id) REFERENCES generation_jobs(project_id,id)
);
ALTER TABLE projects ADD CONSTRAINT project_head_fk FOREIGN KEY(id,head_revision_id) REFERENCES song_revisions(project_id,id);
ALTER TABLE generation_jobs ADD CONSTRAINT job_base_fk FOREIGN KEY(project_id,base_revision_id) REFERENCES song_revisions(project_id,id);
ALTER TABLE generation_jobs ADD CONSTRAINT job_result_fk FOREIGN KEY(project_id,result_revision_id) REFERENCES song_revisions(project_id,id);
CREATE INDEX job_claim_idx ON generation_jobs(created_at,id) WHERE state = 'queued';
CREATE INDEX job_lease_idx ON generation_jobs(lease_expires_at) WHERE state IN ('preparing','running','postprocessing');
CREATE INDEX jobs_project_idx ON generation_jobs(project_id,created_at DESC,id DESC);
CREATE INDEX refs_project_idx ON reference_tracks(project_id,created_at DESC,id DESC);
CREATE INDEX revisions_project_idx ON song_revisions(project_id,created_at DESC,id DESC);
