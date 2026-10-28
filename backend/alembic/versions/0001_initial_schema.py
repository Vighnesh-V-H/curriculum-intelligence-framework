from pathlib import Path

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "001_initial_schema.sql"

TABLES = [
    "audit_logs",
    "verification_finding_references",
    "verification_findings",
    "verification_runs",
    "course_prerequisites",
    "co_po_mapping_versions",
    "co_po_mappings",
    "mapping_levels",
    "curriculum_version_peos",
    "curriculum_version_program_outcomes",
    "peo_versions",
    "program_educational_objectives",
    "program_outcome_versions",
    "program_outcomes",
    "course_outcomes",
    "courses",
    "course_types",
    "semesters",
    "curriculum_versions",
    "curricula",
    "programs",
    "departments",
    "user_roles",
    "roles",
    "users",
]


def upgrade() -> None:
    op.execute(SQL_FILE.read_text(encoding="utf-8"))


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE")
