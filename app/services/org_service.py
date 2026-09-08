"""Organization, membership, and project business logic."""

import re
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Membership, Organization, Project, User
from app.repositories.org_repository import OrgRepository
from app.repositories.user_repository import UserRepository
from app.schemas import MemberInvite, OrganizationCreate, ProjectCreate


class OrgService:
    """Handle tenant and project operations with membership authorization."""

    @staticmethod
    def list_organizations(db: Session, user: User) -> list[Organization]:
        """Return organizations where the user has a membership."""

        return OrgRepository.list_organizations(db, user.id)

    @staticmethod
    def create_organization(
        db: Session, user: User, organization_data: OrganizationCreate
    ) -> Organization:
        """Create an organization and make the creator its owner."""

        name = organization_data.name.strip()
        if not name:
            raise ValueError("Organization name cannot be empty")

        slug = OrgService._slugify(name)
        if OrgRepository.get_by_slug(db, slug) is not None:
            raise ValueError("Organization slug already exists")

        organization = Organization(name=name, slug=slug)
        membership = Membership(
            user_id=user.id,
            organization_id=organization.id,
            role="owner",
        )

        try:
            OrgRepository.save_organization(db, organization, membership)
        except IntegrityError as exc:
            OrgRepository.rollback(db)
            raise ValueError("Organization slug already exists") from exc

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
        invited_user = UserRepository.get_by_email(db, email)
        if invited_user is None:
            raise LookupError("User not found")

        existing_membership = OrgRepository.get_membership(
            db, invited_user.id, organization_id
        )
        if existing_membership is not None:
            raise ValueError("User is already a member of this organization")

        membership = Membership(
            user_id=invited_user.id,
            organization_id=organization_id,
            role=invite.role,
        )
        try:
            OrgRepository.save_membership(db, membership)
        except IntegrityError as exc:
            OrgRepository.rollback(db)
            raise ValueError("User is already a member of this organization") from exc

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

        existing_project = OrgRepository.get_project_by_key(db, organization_id, key)
        if existing_project is not None:
            raise ValueError("Project key already exists in this organization")

        project = Project(
            organization_id=organization_id,
            name=name,
            key=key,
        )
        try:
            OrgRepository.save_project(db, project)
        except IntegrityError as exc:
            OrgRepository.rollback(db)
            raise ValueError("Project key already exists in this organization") from exc

        return project

    @staticmethod
    def list_projects(
        db: Session, actor: User, organization_id: UUID
    ) -> list[Project]:
        """Return projects visible to a member of an organization."""

        OrgService._require_member(db, actor, organization_id)
        return OrgRepository.list_projects(db, organization_id)

    @staticmethod
    def _require_member(db: Session, user: User, organization_id: UUID) -> Membership:
        membership = OrgRepository.get_membership(db, user.id, organization_id)
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
