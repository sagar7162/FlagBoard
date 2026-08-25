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
