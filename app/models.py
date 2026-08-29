"""SQLAlchemy ORM models for users and organizations."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """A user who can belong to one or more organizations."""

    __tablename__ = "user"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Organization(Base):
    """A tenant containing projects and feature flags."""

    __tablename__ = "organization"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class Membership(Base):
    """Associates a user with an organization and their role in it."""

    __tablename__ = "membership"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id"),
        CheckConstraint("role IN ('owner', 'member')", name="membership_role_check"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organization.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)

    user: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship(back_populates="memberships")


class Project(Base):
    """A project containing an organization's feature flags."""

    __tablename__ = "project"
    __table_args__ = (UniqueConstraint("organization_id", "key"),)

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organization.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    key: Mapped[str] = mapped_column(String, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="projects")
    flags: Mapped[list["Flag"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Flag(Base):
    """A boolean feature flag belonging to a project."""

    __tablename__ = "flag"
    __table_args__ = (UniqueConstraint("project_id", "key"),)

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("project.id"), nullable=False
    )
    key: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    on_value: Mapped[bool] = mapped_column(
        default=True, nullable=False, server_default="true"
    )
    off_value: Mapped[bool] = mapped_column(
        default=False, nullable=False, server_default="false"
    )
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="flags")
    environment_configs: Mapped[list["FlagEnvironmentConfig"]] = relationship(
        back_populates="flag", cascade="all, delete-orphan"
    )


class FlagEnvironmentConfig(Base):
    """One environment's settings for a feature flag."""

    __tablename__ = "flag_environment_config"
    __table_args__ = (
        UniqueConstraint("flag_id", "environment"),
        CheckConstraint(
            "environment IN ('development', 'staging', 'production')",
            name="flag_environment_check",
        ),
        CheckConstraint(
            "rollout_percentage IS NULL OR rollout_percentage BETWEEN 0 AND 100",
            name="rollout_percentage_check",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    flag_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("flag.id"), nullable=False
    )
    environment: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        default=False, nullable=False, server_default="false"
    )
    rollout_percentage: Mapped[int | None] = mapped_column(nullable=True)
    rule_attribute: Mapped[str | None] = mapped_column(String, nullable=True)
    rule_operator: Mapped[str | None] = mapped_column(String, nullable=True)
    rule_value: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    flag: Mapped[Flag] = relationship(back_populates="environment_configs")


class ApiKey(Base):
    """An environment-scoped API key for flag evaluation."""

    __tablename__ = "api_key"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organization.id"), nullable=False
    )
    environment: Mapped[str] = mapped_column(String, nullable=False)
    hashed_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    organization: Mapped[Organization] = relationship(back_populates="api_keys")
