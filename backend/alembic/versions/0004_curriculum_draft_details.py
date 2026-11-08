import sqlalchemy as sa
from alembic import op

revision = "0004_curriculum_draft_details"
down_revision = "0003_document_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("curricula", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("semesters", sa.Column("focus", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("semesters", "focus")
    op.drop_column("curricula", "description")
