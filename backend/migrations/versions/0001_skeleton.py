"""Initial project, assets, references, jobs and immutable revision schema."""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    sql = Path(__file__).with_suffix(".sql").read_text(encoding="utf-8")
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    op.execute("ALTER TABLE projects DROP CONSTRAINT project_head_fk")
    op.execute("ALTER TABLE generation_jobs DROP CONSTRAINT job_result_fk")
    op.execute("ALTER TABLE generation_jobs DROP CONSTRAINT job_base_fk")
    for table in ("song_revisions", "generation_jobs", "reference_tracks", "assets", "projects"):
        op.drop_table(table)
