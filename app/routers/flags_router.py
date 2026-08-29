"""Feature-flag mutation endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Flag, User
from app.schemas import (
    FlagCreate,
    FlagResponse,
    FlagRolloutUpdate,
    FlagRuleUpdate,
    FlagToggle,
)
from app.services.flag_service import FlagService


router = APIRouter(tags=["flags"])
Environment = Annotated[str, "development, staging, or production"]


@router.post("/projects/{project_id}/flags", response_model=FlagResponse)
def create_flag(
    project_id: UUID,
    flag_data: FlagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Flag:
    """Create a flag in a project."""

    try:
        return FlagService.create_flag(db, current_user, project_id, flag_data)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch(
    "/flags/{flag_id}/environments/{environment}/toggle",
    response_model=FlagResponse,
)
def toggle_flag(
    flag_id: UUID,
    environment: Environment,
    update: FlagToggle,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Flag:
    """Enable or disable a flag in one environment."""

    try:
        return FlagService.toggle_flag(
            db, current_user, flag_id, environment, update.enabled
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch(
    "/flags/{flag_id}/environments/{environment}/rollout",
    response_model=FlagResponse,
)
def update_rollout(
    flag_id: UUID,
    environment: Environment,
    update: FlagRolloutUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Flag:
    """Set a flag's percentage rollout in one environment."""

    try:
        return FlagService.update_rollout(
            db, current_user, flag_id, environment, update.percentage
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch(
    "/flags/{flag_id}/environments/{environment}/rule",
    response_model=FlagResponse,
)
def update_rule(
    flag_id: UUID,
    environment: Environment,
    rule: FlagRuleUpdate | None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Flag:
    """Set or clear a flag's targeting rule in one environment."""

    try:
        return FlagService.update_rule(
            db, current_user, flag_id, environment, rule
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
