"""Make curriculum content immediately editable and effective.

Revision ID: 0008_remove_curriculum_approval_workflow
Revises: 0007_allow_multiple_curricula_per_program
"""

from alembic import op

revision = "0008_remove_curriculum_approval_workflow"
down_revision = "0007_allow_multiple_curricula_per_program"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE curriculum_versions SET status = 'APPROVED' "
        "WHERE status IN ('DRAFT', 'UNDER_REVIEW')"
    )
    op.execute(
        "UPDATE program_outcome_versions SET status = 'APPROVED' "
        "WHERE status IN ('DRAFT', 'PROPOSED', 'REJECTED')"
    )
    op.execute(
        "UPDATE peo_versions SET status = 'APPROVED' "
        "WHERE status IN ('DRAFT', 'PROPOSED', 'REJECTED')"
    )
    op.execute(
        "UPDATE co_po_mapping_versions SET status = 'APPROVED' "
        "WHERE status IN ('DRAFT', 'PROPOSED', 'REJECTED')"
    )
    op.execute(
        "UPDATE course_prerequisites SET status = 'APPROVED' "
        "WHERE status = 'PROPOSED'"
    )


def downgrade() -> None:
    # Workflow states are intentionally not reconstructed: they were a product
    # approval gate and do not have a reliable reverse mapping.
    pass
