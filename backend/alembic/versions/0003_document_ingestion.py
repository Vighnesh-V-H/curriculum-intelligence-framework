from pathlib import Path

from alembic import op

revision = "0003_document_ingestion"
down_revision = "0002_seed_reference_data"
branch_labels = None
depends_on = None

SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "003_document_ingestion.sql"


def upgrade() -> None:
    op.execute(SQL_FILE.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS documents CASCADE")
