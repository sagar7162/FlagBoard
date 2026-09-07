"""HTTP integration tests for flag APIs and tenant isolation."""

from uuid import uuid4

from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str) -> str:
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": "correct horse battery staple"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_flag_for_user(client: TestClient, token: str) -> tuple[str, str, str]:
    headers = _authorization(token)
    organization = client.post(
        "/orgs", headers=headers, json={"name": f"Acme {uuid4().hex}"}
    )
    assert organization.status_code == 200, organization.text
    organization_id = organization.json()["id"]

    project = client.post(
        f"/orgs/{organization_id}/projects",
        headers=headers,
        json={"name": "Web", "key": "web"},
    )
    assert project.status_code == 200, project.text
    project_id = project.json()["id"]

    flag = client.post(
        f"/projects/{project_id}/flags",
        headers=headers,
        json={"key": "checkout", "name": "New checkout"},
    )
    assert flag.status_code == 200, flag.text
    return organization_id, project_id, flag.json()["id"]


def test_flag_lifecycle_uses_real_http_and_postgres(client: TestClient):
    """Exercise authentication, persistence, mutation, and evaluation end to end."""

    token = _signup(client, f"owner-{uuid4().hex}@example.com")
    headers = _authorization(token)
    organization_id, project_id, flag_id = _create_flag_for_user(client, token)

    api_key = client.post(
        f"/orgs/{organization_id}/api-keys",
        headers=headers,
        json={"environment": "production"},
    )
    assert api_key.status_code == 201, api_key.text

    toggle = client.patch(
        f"/flags/{flag_id}/environments/production/toggle",
        headers=headers,
        json={"enabled": True},
    )
    assert toggle.status_code == 200, toggle.text

    flags = client.get(f"/projects/{project_id}/flags", headers=headers)
    assert flags.status_code == 200, flags.text
    assert flags.json()[0]["key"] == "checkout"

    evaluation = client.post(
        "/evaluate/checkout",
        headers={"Authorization": f"ApiKey {api_key.json()['raw_key']}"},
        json={"user": {"key": "user-123"}},
    )
    assert evaluation.status_code == 200, evaluation.text
    assert evaluation.json()["value"] is True
    assert evaluation.json()["reason"] == "default_on"


def test_tenant_isolation_is_enforced_over_real_http_and_database(client: TestClient):
    """A user in another tenant cannot read or mutate the first tenant's flag."""

    user_a_token = _signup(client, f"user-a-{uuid4().hex}@example.com")
    _, project_id, flag_id = _create_flag_for_user(client, user_a_token)

    user_b_token = _signup(client, f"user-b-{uuid4().hex}@example.com")
    user_b_headers = _authorization(user_b_token)

    get_flag = client.get(f"/flags/{flag_id}", headers=user_b_headers)
    assert get_flag.status_code == 404, get_flag.text

    list_flags = client.get(
        f"/projects/{project_id}/flags", headers=user_b_headers
    )
    assert list_flags.status_code == 403, list_flags.text

    toggle_flag = client.patch(
        f"/flags/{flag_id}/environments/production/toggle",
        headers=user_b_headers,
        json={"enabled": True},
    )
    assert toggle_flag.status_code == 404, toggle_flag.text
