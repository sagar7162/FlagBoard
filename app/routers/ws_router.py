"""Organization-scoped dashboard WebSocket endpoint."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import verify_access_token
from app.database import get_db
from app.models import Membership, User
from app.realtime import connection_manager


router = APIRouter(tags=["realtime"])
DbSession = Annotated[Session, Depends(get_db)]


@router.websocket("/ws/orgs/{org_id}")
async def organization_websocket(
    websocket: WebSocket,
    org_id: UUID,
    token: str,
    db: DbSession,
) -> None:
    """Keep an authenticated organization's dashboard socket connected."""

    if not _is_org_member(db, token, org_id):
        await websocket.close(code=1008)
        return

    organization_key = str(org_id)
    await connection_manager.connect(organization_key, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connection_manager.disconnect(organization_key, websocket)


def _is_org_member(db: Session, token: str, organization_id: UUID) -> bool:
    """Return whether a valid JWT identifies a member of the organization."""

    try:
        payload = verify_access_token(token)
        subject = payload.get("sub")
        if not isinstance(subject, str):
            return False
        user_id = UUID(subject)
    except (TypeError, ValueError):
        return False

    if db.get(User, user_id) is None:
        return False

    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
        )
    )
    return membership is not None
