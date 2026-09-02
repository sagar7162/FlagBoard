"""create projects, flags, environment configs, and API keys

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key"),
    )
    op.create_table(
        "flag",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("on_value", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("off_value", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "key"),
    )
    op.create_table(
        "flag_environment_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("flag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("rollout_percentage", sa.Integer(), nullable=True),
        sa.Column("rule_attribute", sa.String(), nullable=True),
        sa.Column("rule_operator", sa.String(), nullable=True),
        sa.Column("rule_value", sa.String(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "environment IN ('development', 'staging', 'production')",
            name="flag_environment_check",
        ),
        sa.CheckConstraint(
            "rollout_percentage IS NULL OR rollout_percentage BETWEEN 0 AND 100",
            name="rollout_percentage_check",
        ),
        sa.ForeignKeyConstraint(["flag_id"], ["flag.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flag_id", "environment"),
    )
    op.create_table(
        "api_key",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(), nullable=False),
        sa.Column("hashed_key", sa.String(), nullable=False),
        sa.Column("key_prefix", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hashed_key"),
    )


def downgrade() -> None:
    op.drop_table("api_key")
    op.drop_table("flag_environment_config")
    op.drop_table("flag")
    op.drop_table("project")
