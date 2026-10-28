from pathlib import Path

from alembic import op

revision = "0002_seed_reference_data"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "002_seed_reference_data.sql"

ROLE_IDS = ", ".join(
    f"'{suffix}'"
    for suffix in [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000003",
        "00000000-0000-0000-0000-000000000004",
    ]
)

COURSE_TYPE_IDS = ", ".join(
    f"'{suffix}'"
    for suffix in [
        "00000000-0000-0000-0000-000000000101",
        "00000000-0000-0000-0000-000000000102",
        "00000000-0000-0000-0000-000000000103",
        "00000000-0000-0000-0000-000000000104",
        "00000000-0000-0000-0000-000000000105",
        "00000000-0000-0000-0000-000000000106",
    ]
)

MAPPING_LEVEL_IDS = ", ".join(
    f"'{suffix}'"
    for suffix in [
        "00000000-0000-0000-0000-000000000201",
        "00000000-0000-0000-0000-000000000202",
        "00000000-0000-0000-0000-000000000203",
    ]
)


def upgrade() -> None:
    op.execute(SQL_FILE.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute(f"DELETE FROM mapping_levels WHERE id IN ({MAPPING_LEVEL_IDS})")
    op.execute(
        f"DELETE FROM course_types WHERE id IN ({COURSE_TYPE_IDS}) "
        "AND NOT EXISTS (SELECT 1 FROM courses WHERE courses.course_type_id = course_types.id)"
    )
    op.execute(
        f"DELETE FROM roles WHERE id IN ({ROLE_IDS}) "
        "AND NOT EXISTS (SELECT 1 FROM user_roles WHERE user_roles.role_id = roles.id)"
    )
