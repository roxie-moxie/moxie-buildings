"""
Shared fixtures for API integration tests.

Uses in-memory SQLite with StaticPool for clean per-test DB isolation.
The real get_db dependency is overridden via app.dependency_overrides.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from moxie.api.main import app
from moxie.api.auth import hash_password
from moxie.db.models import Base, User
from moxie.db.session import get_db


# ---------------------------------------------------------------------------
# Core DB engine and session factory (shared across the module, isolated per test)
# ---------------------------------------------------------------------------

def _make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_test_user(
    db,
    email: str,
    password: str,
    role: str = "agent",
    is_active: bool = True,
) -> User:
    """Create a User with a hashed password and add to DB."""
    user = User(
        name=email.split("@")[0],
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_auth_header(client: TestClient, email: str, password: str) -> dict:
    """Log in via POST /auth/login and return Authorization header dict."""
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    """Yield a TestingSession backed by in-memory SQLite. Clean per test."""
    engine = _make_engine()
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSession()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session):
    """Yield a FastAPI TestClient with get_db overridden to use the test DB session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # session lifecycle managed by db_session fixture

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def admin_user(db_session):
    """Create and return an active admin user."""
    return create_test_user(db_session, "admin@test.com", "adminpass123", role="admin")


@pytest.fixture()
def admin_headers(client, admin_user):
    """Return Authorization headers for the admin user."""
    return get_auth_header(client, "admin@test.com", "adminpass123")


@pytest.fixture()
def agent_user(db_session):
    """Create and return an active agent user."""
    return create_test_user(db_session, "agent@test.com", "agentpass123", role="agent")


@pytest.fixture()
def agent_headers(client, agent_user):
    """Return Authorization headers for the agent user."""
    return get_auth_header(client, "agent@test.com", "agentpass123")
