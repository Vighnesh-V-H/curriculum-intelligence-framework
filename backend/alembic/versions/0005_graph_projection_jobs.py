import sqlalchemy as sa

from alembic import op

revision = "0005_graph_projection_jobs"
down_revision = "0004_curriculum_draft_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "graph_projection_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("worker_id", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["curriculum_version_id"],
            ["curriculum_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_graph_projection_jobs_status_requested",
        "graph_projection_jobs",
        ["status", "requested_at"],
    )
    op.create_index(
        "ix_graph_projection_jobs_version_requested",
        "graph_projection_jobs",
        ["curriculum_version_id", "requested_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_graph_projection_jobs_version_requested", table_name="graph_projection_jobs")
    op.drop_index("ix_graph_projection_jobs_status_requested", table_name="graph_projection_jobs")
    op.drop_table("graph_projection_jobs")
