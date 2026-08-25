"""Organization, membership, and project endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Membership, Organization, Project, User
from app.schemas import (
    MemberInvite,
    MembershipResponse,
    OrganizationCreate,
    OrganizationResponse,
    ProjectCreate,
    ProjectResponse,
)
from app.services.org_service import OrgService


router = APIRouter(prefix="/orgs", tags=["organizations"])


@router.post("", response_model=OrganizationResponse)
def create_organization(
    organization_data: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Organization:
    """Create an organization owned by the authenticated user."""

    try:
        return OrgService.create_organization(db, current_user, organization_data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{organization_id}/members", response_model=MembershipResponse)
def invite_member(
    organization_id: UUID,
    invite: MemberInvite,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Membership:
    """Invite an existing user to an organization."""

    try:
        return OrgService.invite_member(db, current_user, organization_id, invite)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{organization_id}/projects", response_model=ProjectResponse)
def create_project(
    organization_id: UUID,
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Project:
    """Create a project for an organization member."""

    try:
        return OrgService.create_project(
            db, current_user, organization_id, project_data
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
