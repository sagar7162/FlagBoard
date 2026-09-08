"""Pydantic schemas for the authentication and organization APIs."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    """Payload used to create a user account."""

    email: str
    password: str


class UserLogin(BaseModel):
    """Payload used to authenticate a user."""

    email: str
    password: str


class Token(BaseModel):
    """JWT returned after successful signup or login."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: datetime


class OrganizationCreate(BaseModel):
    """Payload used to create an organization."""

    name: str


class OrganizationResponse(BaseModel):
    """Organization representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    created_at: datetime


class ApiKeyCreate(BaseModel):
    """Payload used to create an environment-scoped evaluation key."""

    environment: Literal["development", "staging", "production"]


class ApiKeyCreateResponse(BaseModel):
    """API key returned once at creation time, including its raw secret."""

    id: UUID
    key_prefix: str
    raw_key: str


class ApiKeyResponse(BaseModel):
    """Public API key metadata; never includes the raw secret."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key_prefix: str
    environment: Literal["development", "staging", "production"]
    created_at: datetime
    revoked_at: datetime | None


class MembershipResponse(BaseModel):
    """Organization membership representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    organization_id: UUID
    role: Literal["owner", "member"]


class MemberInvite(BaseModel):
    """Payload used to add an existing user to an organization."""

    email: str
    role: Literal["owner", "member"] = "member"


class ProjectCreate(BaseModel):
    """Payload used to create a project."""

    name: str
    key: str


class ProjectResponse(BaseModel):
    """Project representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    key: str


class FlagCreate(BaseModel):
    """Payload used to create a boolean feature flag."""

    key: str
    name: str


class FlagToggle(BaseModel):
    """Payload used to enable or disable a flag in one environment."""

    enabled: bool


class FlagRolloutUpdate(BaseModel):
    """Payload used to update a percentage rollout."""

    percentage: int


class FlagRuleUpdate(BaseModel):
    """The single targeting rule supported by v1."""

    attribute: str
    operator: Literal["equals"]
    value: str


class EnvironmentConfigResponse(BaseModel):
    """One environment's settings for a feature flag."""

    model_config = ConfigDict(from_attributes=True)

    environment: str
    enabled: bool
    rollout_percentage: int | None
    rule_attribute: str | None
    rule_operator: str | None
    rule_value: str | None
    updated_at: datetime


class FlagResponse(BaseModel):
    """Flag representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    organization_id: UUID
    flag_id: UUID
    actor_user_id: UUID
    action: str
    before: dict[str, object] | None
    after: dict[str, object] | None
    created_at: datetime


class EvaluationUser(BaseModel):
    """Client user identity and attributes used during evaluation."""

    key: str
    attributes: dict[str, object] = Field(default_factory=dict)


class EvaluationRequest(BaseModel):
    """Payload submitted to the flag evaluation endpoint."""

    user: EvaluationUser


class EvaluationResponse(BaseModel):
    """Resolved flag value and evaluation reason."""

    flag_key: str
    value: bool
    reason: str
