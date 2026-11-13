import sqlalchemy as sa

from alembic import op

revision = "0006_verification_references"
down_revision = "0005_graph_projection_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verification_references",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("program_id", sa.Uuid(), nullable=True),
        sa.Column("reference_type", sa.String(length=30), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=300), nullable=False),
        sa.Column("version_label", sa.String(length=50), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "program_id",
            "reference_type",
            "code",
            "version_label",
            name="uq_verification_references_scope",
        ),
    )
    op.create_index(
        "idx_verification_references_program",
        "verification_references",
        ["program_id", "reference_type", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_verification_references_program",
        table_name="verification_references",
    )
    op.drop_table("verification_references")
