"""scope flag keys to organizations

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "flag",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE flag
            SET organization_id = project.organization_id
            FROM project
            WHERE flag.project_id = project.id
            """
        )
    )
    op.alter_column("flag", "organization_id", nullable=False)
    op.create_foreign_key(
        "fk_flag_organization_id_organization",
        "flag",
        "organization",
        ["organization_id"],
        ["id"],
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for constraint in inspector.get_unique_constraints("flag"):
        if constraint.get("column_names") == ["project_id", "key"]:
            op.drop_constraint(constraint["name"], "flag", type_="unique")

    op.create_unique_constraint(
        "uq_flag_organization_key", "flag", ["organization_id", "key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_flag_organization_key", "flag", type_="unique")
    op.drop_constraint(
        "fk_flag_organization_id_organization", "flag", type_="foreignkey"
    )
    op.create_unique_constraint(
        "uq_flag_project_key", "flag", ["project_id", "key"]
    )
    op.drop_column("flag", "organization_id")
