"""Organization, membership, and project business logic."""

import re
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Membership, Organization, Project, User
from app.schemas import MemberInvite, OrganizationCreate, ProjectCreate


class OrgService:
    """Handle tenant and project operations with membership authorization."""

    @staticmethod
    def create_organization(
        db: Session, user: User, organization_data: OrganizationCreate
    ) -> Organization:
        """Create an organization and make the creator its owner."""

        name = organization_data.name.strip()
        if not name:
            raise ValueError("Organization name cannot be empty")

        slug = OrgService._slugify(name)
        if db.scalar(select(Organization).where(Organization.slug == slug)) is not None:
            raise ValueError("Organization slug already exists")

        organization = Organization(name=name, slug=slug)
        db.add(organization)

        try:
            db.flush()
            db.add(
                Membership(
                    user_id=user.id,
                    organization_id=organization.id,
                    role="owner",
                )
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("Organization slug already exists") from exc

        db.refresh(organization)
        return organization

    @staticmethod
    def invite_member(
        db: Session,
        actor: User,
        organization_id: UUID,
        invite: MemberInvite,
    ) -> Membership:
        """Add an existing user to an organization; owners only."""

        OrgService._require_owner(db, actor, organization_id)
        email = invite.email.strip().lower()
        invited_user = db.scalar(select(User).where(User.email == email))
        if invited_user is None:
            raise LookupError("User not found")

        existing_membership = db.scalar(
            select(Membership).where(
                Membership.user_id == invited_user.id,
                Membership.organization_id == organization_id,
            )
        )
        if existing_membership is not None:
            raise ValueError("User is already a member of this organization")

        membership = Membership(
            user_id=invited_user.id,
            organization_id=organization_id,
            role=invite.role,
        )
        db.add(membership)

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("User is already a member of this organization") from exc

        db.refresh(membership)
        return membership

    @staticmethod
    def create_project(
        db: Session,
        actor: User,
        organization_id: UUID,
        project_data: ProjectCreate,
    ) -> Project:
        """Create a project for an organization member."""

        OrgService._require_member(db, actor, organization_id)
        name = project_data.name.strip()
        key = project_data.key.strip()
        if not name or not key:
            raise ValueError("Project name and key cannot be empty")

        existing_project = db.scalar(
            select(Project).where(
                Project.organization_id == organization_id,
                Project.key == key,
            )
        )
        if existing_project is not None:
            raise ValueError("Project key already exists in this organization")

        project = Project(
            organization_id=organization_id,
            name=name,
            key=key,
        )
        db.add(project)

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("Project key already exists in this organization") from exc

        db.refresh(project)
        return project

    @staticmethod
    def list_projects(
        db: Session, actor: User, organization_id: UUID
    ) -> list[Project]:
        """Return projects visible to a member of an organization."""

        OrgService._require_member(db, actor, organization_id)
        return list(
            db.scalars(
                select(Project)
                .where(Project.organization_id == organization_id)
                .order_by(Project.name)
            ).all()
        )

    @staticmethod
    def _require_member(db: Session, user: User, organization_id: UUID) -> Membership:
        membership = db.scalar(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.organization_id == organization_id,
            )
        )
        if membership is None:
            raise PermissionError("User is not a member of this organization")
        return membership

    @staticmethod
    def _require_owner(db: Session, user: User, organization_id: UUID) -> Membership:
        membership = OrgService._require_member(db, user, organization_id)
        if membership.role != "owner":
            raise PermissionError("Only organization owners can invite members")
        return membership

    @staticmethod
    def _slugify(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return slug or f"organization-{uuid4().hex[:8]}"
