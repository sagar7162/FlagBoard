"""Organization, membership, and project endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import ApiKey, Membership, Organization, Project, User
from app.schemas import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    MemberInvite,
    MembershipResponse,
    OrganizationCreate,
    OrganizationResponse,
    ProjectCreate,
    ProjectResponse,
)
from app.services.api_key_service import ApiKeyService
from app.services.org_service import OrgService


router = APIRouter(prefix="/orgs", tags=["organizations"])


@router.get("", response_model=list[OrganizationResponse])
def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Organization]:
    """Return organizations where the authenticated user is a member."""

    return OrgService.list_organizations(db, current_user)


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


@router.post(
    "/{organization_id}/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_api_key(
    organization_id: UUID,
    key_data: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiKeyCreateResponse:
    """Create an evaluation API key; owners only."""

    try:
        api_key, raw_key = ApiKeyService.create(
            db, current_user, organization_id, key_data.environment
        )
        return ApiKeyCreateResponse(
            id=api_key.id,
            key_prefix=api_key.key_prefix,
            raw_key=raw_key,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/{organization_id}/api-keys", response_model=list[ApiKeyResponse])
def list_api_keys(
    organization_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ApiKey]:
    """List API-key metadata for organization members."""

    try:
        return ApiKeyService.list_for_organization(db, current_user, organization_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.delete("/{organization_id}/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    organization_id: UUID,
    api_key_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Revoke an evaluation API key; owners only."""

    try:
        ApiKeyService.revoke(db, current_user, organization_id, api_key_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.get("/{organization_id}/projects", response_model=list[ProjectResponse])
def list_projects(
    organization_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Project]:
    """Return projects for an organization member."""

    try:
        return OrgService.list_projects(db, current_user, organization_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


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
