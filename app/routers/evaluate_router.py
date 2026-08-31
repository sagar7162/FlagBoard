"""API-key-authenticated flag evaluation endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_api_key_context
from app.cache import cache
from app.database import get_db
from app.models import ApiKey
from app.schemas import EvaluationRequest, EvaluationResponse
from app.services.evaluation_service import EvaluationService


router = APIRouter(tags=["evaluation"])


@router.post("/evaluate/{flag_key}", response_model=EvaluationResponse)
def evaluate_flag(
    flag_key: str,
    request: EvaluationRequest,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key_context),
) -> EvaluationResponse:
    """Evaluate a flag for a user in the API key's environment."""

    return EvaluationService.evaluate(db, api_key, flag_key, request.user, cache)
