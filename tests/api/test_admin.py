"""
Integration tests for admin endpoints.

Covers:
- POST /admin/users (ADMIN-01): create agent, duplicate email, short password, role check
- PATCH /admin/users/{id}/deactivate (ADMIN-02): deactivate, login rejected, token rejected, 404, role check
- GET /admin/buildings (ADMIN-03): list buildings, ordering, role check
"""
from moxie.db.models import Building
from tests.api.conftest import create_test_user


class TestCreateUser:
    def test_admin_creates_agent(self, client, admin_headers):
        resp = client.post(
            "/admin/users",
            json={"name": "New Agent", "email": "newagent@test.com", "password": "securepass"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "agent"
        assert data["is_active"] is True
        assert data["email"] == "newagent@test.com"

    def test_duplicate_email_returns_409(self, client, admin_headers, agent_user):
        # agent_user already has email agent@test.com
        resp = client.post(
            "/admin/users",
            json={"name": "Duplicate", "email": "agent@test.com", "password": "securepass"},
            headers=admin_headers,
        )
        assert resp.status_code == 409

    def test_short_password_rejected(self, client, admin_headers):
        resp = client.post(
            "/admin/users",
            json={"name": "Shorty", "email": "shorty@test.com", "password": "short"},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_agent_cannot_create_user(self, client, agent_headers):
        resp = client.post(
            "/admin/users",
            json={"name": "Sneaky", "email": "sneaky@test.com", "password": "securepass"},
            headers=agent_headers,
        )
        assert resp.status_code == 403


class TestDeactivateUser:
    def test_admin_deactivates_agent(self, client, admin_headers, agent_user):
        resp = client.patch(
            f"/admin/users/{agent_user.id}/deactivate",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_deactivated_agent_cannot_login(self, client, admin_headers, agent_user):
        # Deactivate
        client.patch(f"/admin/users/{agent_user.id}/deactivate", headers=admin_headers)
        # Try login
        resp = client.post("/auth/login", json={"email": "agent@test.com", "password": "agentpass123"})
        assert resp.status_code == 401

    def test_deactivated_agent_jwt_rejected(self, client, admin_headers, agent_user, agent_headers):
        # Confirm agent token works initially
        resp = client.get("/units", headers=agent_headers)
        assert resp.status_code == 200

        # Admin deactivates agent
        client.patch(f"/admin/users/{agent_user.id}/deactivate", headers=admin_headers)

        # Same token now rejected
        resp = client.get("/units", headers=agent_headers)
        assert resp.status_code == 401

    def test_deactivate_nonexistent_user_returns_404(self, client, admin_headers):
        resp = client.patch("/admin/users/99999/deactivate", headers=admin_headers)
        assert resp.status_code == 404

    def test_agent_cannot_deactivate(self, client, agent_headers, agent_user):
        resp = client.patch(
            f"/admin/users/{agent_user.id}/deactivate",
            headers=agent_headers,
        )
        assert resp.status_code == 403


class TestListBuildings:
    def test_admin_lists_buildings(self, client, admin_headers, db_session):
        b1 = Building(
            name="Building One",
            url="https://building-one.com",
            neighborhood="River North",
            platform="sightmap",
        )
        b2 = Building(
            name="Building Two",
            url="https://building-two.com",
            neighborhood="Loop",
            platform="rentcafe",
        )
        db_session.add_all([b1, b2])
        db_session.commit()

        resp = client.get("/admin/buildings", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Verify expected fields are present
        for item in data:
            assert "name" in item
            assert "url" in item
            assert "platform" in item
            assert "last_scraped_at" in item

    def test_agent_cannot_list_buildings(self, client, agent_headers):
        resp = client.get("/admin/buildings", headers=agent_headers)
        assert resp.status_code == 403

    def test_buildings_ordered_by_name(self, client, admin_headers, db_session):
        zebra = Building(name="Zebra", url="https://zebra.com", platform="sightmap")
        alpha = Building(name="Alpha", url="https://alpha.com", platform="sightmap")
        db_session.add_all([zebra, alpha])
        db_session.commit()

        resp = client.get("/admin/buildings", headers=admin_headers)
        assert resp.status_code == 200
        names = [b["name"] for b in resp.json()]
        assert names == sorted(names)
        assert names[0] == "Alpha"
        assert names[-1] == "Zebra"
