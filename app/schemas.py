"""Pydantic schemas for the authentication and organization APIs."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
