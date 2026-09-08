"""Persistence operations for organizations, memberships, and projects."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Membership, Organization, Project


class OrgRepository:
    """Keep organization-scoped queries and writes out of organization services."""

    @staticmethod
    def list_organizations(db: Session, user_id: UUID) -> list[Organization]:
        statement = (
            select(Organization)
            .join(Membership)
            .where(Membership.user_id == user_id)
            .order_by(Organization.name)
        )
        return list(db.scalars(statement).all())

    @staticmethod
    def get_by_slug(db: Session, slug: str) -> Organization | None:
        return db.scalar(select(Organization).where(Organization.slug == slug))

    @staticmethod
    def get_membership(
        db: Session, user_id: UUID, organization_id: UUID
    ) -> Membership | None:
        return db.scalar(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.organization_id == organization_id,
            )
        )

    @staticmethod
    def get_project(db: Session, project_id: UUID) -> Project | None:
        return db.get(Project, project_id)

    @staticmethod
    def get_project_by_key(
        db: Session, organization_id: UUID, key: str
    ) -> Project | None:
        return db.scalar(
            select(Project).where(
                Project.organization_id == organization_id,
                Project.key == key,
            )
        )

    @staticmethod
    def list_projects(db: Session, organization_id: UUID) -> list[Project]:
        statement = (
            select(Project)
            .where(Project.organization_id == organization_id)
            .order_by(Project.name)
        )
        return list(db.scalars(statement).all())

    @staticmethod
    def save_organization(
        db: Session, organization: Organization, membership: Membership
    ) -> Organization:
        db.add(organization)
        db.flush()
        membership.organization_id = organization.id
        db.add(membership)
        db.commit()
        db.refresh(organization)
        return organization

    @staticmethod
    def save_membership(db: Session, membership: Membership) -> Membership:
        db.add(membership)
        db.commit()
        db.refresh(membership)
        return membership

    @staticmethod
    def save_project(db: Session, project: Project) -> Project:
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def rollback(db: Session) -> None:
        db.rollback()
