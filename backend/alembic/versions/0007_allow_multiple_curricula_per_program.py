"""Allow multiple curricula for the same program and regulation.

Revision ID: 0007_allow_multiple_curricula_per_program
Revises: 0006_verification_references
"""

from alembic import op

revision = "0007_allow_multiple_curricula_per_program"
down_revision = "0006_verification_references"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_curricula_program_regulation", "curricula", type_="unique"
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_curricula_program_regulation", "curricula", ["program_id", "regulation"]
    )
