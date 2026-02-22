"""
Integration tests for authentication endpoints.

Covers:
- POST /auth/login: success, invalid credentials, inactive account
- JWT protection: missing token, bad token, expired token, deactivated user
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from moxie.api.settings import get_settings
from tests.api.conftest import create_test_user


class TestLogin:
    def test_login_valid_credentials(self, client, admin_user):
        resp = client.post("/auth/login", json={"email": "admin@test.com", "password": "adminpass123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_email(self, client, admin_user):
        resp = client.post("/auth/login", json={"email": "nobody@test.com", "password": "adminpass123"})
        assert resp.status_code == 401

    def test_login_invalid_password(self, client, admin_user):
        resp = client.post("/auth/login", json={"email": "admin@test.com", "password": "wrongpassword"})
        assert resp.status_code == 401

    def test_login_inactive_account(self, client, db_session):
        create_test_user(db_session, "inactive@test.com", "pass1234", role="agent", is_active=False)
        resp = client.post("/auth/login", json={"email": "inactive@test.com", "password": "pass1234"})
        assert resp.status_code == 401
        assert "inactive" in resp.json()["detail"].lower()

    def test_login_returns_working_jwt(self, client, admin_user):
        login_resp = client.post("/auth/login", json={"email": "admin@test.com", "password": "adminpass123"})
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        health_resp = client.get("/health")
        assert health_resp.status_code == 200
        # Also verify the token works for a protected endpoint
        units_resp = client.get("/units", headers={"Authorization": f"Bearer {token}"})
        assert units_resp.status_code == 200


class TestAuthProtection:
    def test_no_token_returns_401(self, client, admin_user):
        # FastAPI HTTPBearer returns 401 when no Authorization header is present
        resp = client.get("/units")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client, admin_user):
        resp = client.get("/units", headers={"Authorization": "Bearer this.is.garbage"})
        assert resp.status_code == 401

    def test_expired_token_returns_401(self, client, admin_user):
        settings = get_settings()
        # Create a token with exp 1 hour in the past
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {"sub": str(admin_user.id), "exp": past}
        expired_token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
        resp = client.get("/units", headers={"Authorization": f"Bearer {expired_token}"})
        assert resp.status_code == 401

    def test_deactivated_user_token_rejected(self, client, db_session, agent_user, agent_headers):
        # First verify the token works
        resp = client.get("/units", headers=agent_headers)
        assert resp.status_code == 200

        # Deactivate the agent directly in DB
        agent_user.is_active = False
        db_session.commit()

        # Same token should now be rejected
        resp = client.get("/units", headers=agent_headers)
        assert resp.status_code == 401
