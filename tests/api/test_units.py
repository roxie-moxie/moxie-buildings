"""
Integration tests for unit search and re-scrape endpoints.

Covers:
- GET /units (AGENT-01): all filter combinations, non-canonical exclusion, response shape
- POST /admin/rescrape/{building_id} (ADMIN-04): trigger, poll, 409 duplicate, 404, role check
"""
from datetime import datetime, timezone
from unittest.mock import patch

from moxie.db.models import Building, Unit
import moxie.api.routers.admin as admin_router_module


# ---------------------------------------------------------------------------
# Seed helper
# ---------------------------------------------------------------------------

def seed_building_with_units(
    db,
    building_name: str,
    neighborhood: str,
    units_data: list[dict],
    platform: str = "sightmap",
) -> Building:
    """
    Create a Building and associated Unit records.

    Each dict in units_data may contain:
        unit_number, bed_type, rent_cents, availability_date
        (optional) floor_plan_name, baths, sqft, non_canonical
    """
    building = Building(
        name=building_name,
        url=f"https://{building_name.lower().replace(' ', '-')}.com",
        neighborhood=neighborhood,
        platform=platform,
    )
    db.add(building)
    db.flush()  # get building.id without committing

    now = datetime.now(timezone.utc)
    for u in units_data:
        unit = Unit(
            building_id=building.id,
            unit_number=u["unit_number"],
            bed_type=u["bed_type"],
            rent_cents=u["rent_cents"],
            availability_date=u["availability_date"],
            floor_plan_name=u.get("floor_plan_name"),
            baths=u.get("baths"),
            sqft=u.get("sqft"),
            non_canonical=u.get("non_canonical", False),
            scrape_run_at=now,
        )
        db.add(unit)

    db.commit()
    db.refresh(building)
    return building


# ---------------------------------------------------------------------------
# Tests: GET /units (AGENT-01)
# ---------------------------------------------------------------------------

class TestUnitSearch:
    def test_search_returns_all_units(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "Test Building", "River North", [
            {"unit_number": "101", "bed_type": "Studio", "rent_cents": 150000, "availability_date": "2026-03-01"},
            {"unit_number": "102", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-04-01"},
            {"unit_number": "103", "bed_type": "2BR", "rent_cents": 250000, "availability_date": "2026-05-01"},
        ])
        resp = client.get("/units", headers=agent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["units"]) == 3

    def test_search_excludes_non_canonical(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "Test Building", "Loop", [
            {"unit_number": "101", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01", "non_canonical": False},
            {"unit_number": "TEMP", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01", "non_canonical": True},
        ])
        resp = client.get("/units", headers=agent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["units"][0]["unit_number"] == "101"

    def test_filter_by_bed_type_single(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "Test Building", "River North", [
            {"unit_number": "101", "bed_type": "Studio", "rent_cents": 150000, "availability_date": "2026-03-01"},
            {"unit_number": "102", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
            {"unit_number": "103", "bed_type": "2BR", "rent_cents": 250000, "availability_date": "2026-03-01"},
        ])
        resp = client.get("/units", params={"beds": "1BR"}, headers=agent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["units"][0]["bed_type"] == "1BR"

    def test_filter_by_bed_type_multi(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "Test Building", "River North", [
            {"unit_number": "101", "bed_type": "Studio", "rent_cents": 150000, "availability_date": "2026-03-01"},
            {"unit_number": "102", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
            {"unit_number": "103", "bed_type": "2BR", "rent_cents": 250000, "availability_date": "2026-03-01"},
        ])
        resp = client.get("/units?beds=1BR&beds=2BR", headers=agent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        bed_types = {u["bed_type"] for u in data["units"]}
        assert bed_types == {"1BR", "2BR"}

    def test_filter_by_rent_min(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "Test Building", "Loop", [
            {"unit_number": "101", "bed_type": "Studio", "rent_cents": 150000, "availability_date": "2026-03-01"},
            {"unit_number": "102", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
            {"unit_number": "103", "bed_type": "2BR", "rent_cents": 250000, "availability_date": "2026-03-01"},
        ])
        # rent_min=2000 means >= $2000 = >= 200000 cents
        resp = client.get("/units", params={"rent_min": 2000}, headers=agent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(u["rent_cents"] >= 200000 for u in data["units"])

    def test_filter_by_rent_max(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "Test Building", "Loop", [
            {"unit_number": "101", "bed_type": "Studio", "rent_cents": 150000, "availability_date": "2026-03-01"},
            {"unit_number": "102", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
            {"unit_number": "103", "bed_type": "2BR", "rent_cents": 250000, "availability_date": "2026-03-01"},
        ])
        # rent_max=2000 means <= $2000 = <= 200000 cents
        resp = client.get("/units", params={"rent_max": 2000}, headers=agent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(u["rent_cents"] <= 200000 for u in data["units"])

    def test_filter_by_rent_range(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "Test Building", "Loop", [
            {"unit_number": "101", "bed_type": "Studio", "rent_cents": 150000, "availability_date": "2026-03-01"},
            {"unit_number": "102", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
            {"unit_number": "103", "bed_type": "2BR", "rent_cents": 250000, "availability_date": "2026-03-01"},
        ])
        resp = client.get("/units", params={"rent_min": 1500, "rent_max": 2000}, headers=agent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        rents = {u["rent_cents"] for u in data["units"]}
        assert rents == {150000, 200000}

    def test_filter_by_available_before(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "Test Building", "River North", [
            {"unit_number": "101", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
            {"unit_number": "102", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-04-01"},
        ])
        resp = client.get("/units", params={"available_before": "2026-03-15"}, headers=agent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["units"][0]["availability_date"] == "2026-03-01"

    def test_available_now_included_with_date_filter(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "Test Building", "River North", [
            {"unit_number": "101", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "Available Now"},
            {"unit_number": "102", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-04-01"},
        ])
        # available_before=2026-03-01 should include "Available Now" unit but not the April unit
        resp = client.get("/units", params={"available_before": "2026-03-01"}, headers=agent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["units"][0]["availability_date"] == "Available Now"

    def test_filter_by_neighborhood_single(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "River North Building", "River North", [
            {"unit_number": "101", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
        ])
        seed_building_with_units(db_session, "Loop Building", "Loop", [
            {"unit_number": "201", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
        ])
        resp = client.get("/units", params={"neighborhood": "River North"}, headers=agent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["units"][0]["neighborhood"] == "River North"

    def test_filter_by_neighborhood_multi(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "River North Building", "River North", [
            {"unit_number": "101", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
        ])
        seed_building_with_units(db_session, "Loop Building", "Loop", [
            {"unit_number": "201", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
        ])
        seed_building_with_units(db_session, "West Loop Building", "West Loop", [
            {"unit_number": "301", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
        ])
        resp = client.get("/units?neighborhood=River+North&neighborhood=Loop", headers=agent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        neighborhoods = {u["neighborhood"] for u in data["units"]}
        assert neighborhoods == {"River North", "Loop"}

    def test_combined_filters(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "River North Building", "River North", [
            {"unit_number": "101", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
            {"unit_number": "102", "bed_type": "2BR", "rent_cents": 300000, "availability_date": "2026-03-01"},
            {"unit_number": "103", "bed_type": "1BR", "rent_cents": 350000, "availability_date": "2026-03-01"},
        ])
        seed_building_with_units(db_session, "Loop Building", "Loop", [
            {"unit_number": "201", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
        ])
        # 1BR, rent <= $2500, River North only
        resp = client.get(
            "/units?beds=1BR&rent_max=2500&neighborhood=River+North",
            headers=agent_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        u = data["units"][0]
        assert u["bed_type"] == "1BR"
        assert u["rent_cents"] <= 250000
        assert u["neighborhood"] == "River North"

    def test_no_filters_returns_all(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "Building A", "River North", [
            {"unit_number": "101", "bed_type": "Studio", "rent_cents": 150000, "availability_date": "2026-03-01"},
            {"unit_number": "102", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-04-01"},
        ])
        seed_building_with_units(db_session, "Building B", "Loop", [
            {"unit_number": "201", "bed_type": "2BR", "rent_cents": 280000, "availability_date": "2026-05-01"},
        ])
        resp = client.get("/units", headers=agent_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    def test_response_includes_building_fields(self, client, agent_headers, db_session):
        seed_building_with_units(db_session, "My Building", "West Loop", [
            {"unit_number": "101", "bed_type": "1BR", "rent_cents": 200000, "availability_date": "2026-03-01"},
        ])
        resp = client.get("/units", headers=agent_headers)
        assert resp.status_code == 200
        unit = resp.json()["units"][0]
        assert unit["building_name"] == "My Building"
        assert unit["building_url"] == "https://my-building.com"
        assert unit["neighborhood"] == "West Loop"
        assert "last_scraped" in unit  # may be None, but field must exist

    def test_unauthenticated_returns_401(self, client, db_session):
        resp = client.get("/units")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tests: POST /admin/rescrape/{building_id} (ADMIN-04)
# ---------------------------------------------------------------------------

MOCK_SCRAPE_RESULT = {"status": "success", "unit_count": 5, "error": None}


class TestRescrape:
    def test_trigger_rescrape_returns_202(self, client, admin_headers, db_session):
        building = seed_building_with_units(db_session, "Rescrape Building", "Loop", [])
        # Patch at the scheduler module level (admin.py uses a local import)
        with patch("moxie.scheduler.runner.scrape_one_building", return_value=MOCK_SCRAPE_RESULT):
            resp = client.post(f"/admin/rescrape/{building.id}", headers=admin_headers)
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "queued"
        assert data["building_id"] == building.id

    def test_rescrape_nonexistent_building_returns_404(self, client, admin_headers):
        resp = client.post("/admin/rescrape/99999", headers=admin_headers)
        assert resp.status_code == 404

    def test_rescrape_duplicate_returns_409(self, client, admin_headers, db_session):
        building = seed_building_with_units(db_session, "Rescrape Building 409", "River North", [])

        # Directly inject an active job into _building_jobs to simulate an in-progress scrape
        fake_job_id = "fake-job-id-409"
        admin_router_module._jobs[fake_job_id] = {
            "job_id": fake_job_id,
            "status": "running",
            "building_id": building.id,
            "unit_count": None,
            "error": None,
            "duration_seconds": None,
        }
        admin_router_module._building_jobs[building.id] = fake_job_id

        try:
            resp = client.post(f"/admin/rescrape/{building.id}", headers=admin_headers)
            assert resp.status_code == 409
        finally:
            # Cleanup to avoid cross-test pollution
            admin_router_module._building_jobs.pop(building.id, None)
            admin_router_module._jobs.pop(fake_job_id, None)

    def test_poll_rescrape_returns_status(self, client, admin_headers, db_session):
        building = seed_building_with_units(db_session, "Poll Building", "Loop", [])
        # Patch at the scheduler module level (admin.py uses a local import)
        with patch("moxie.scheduler.runner.scrape_one_building", return_value=MOCK_SCRAPE_RESULT):
            trigger_resp = client.post(f"/admin/rescrape/{building.id}", headers=admin_headers)
        assert trigger_resp.status_code == 202
        job_id = trigger_resp.json()["job_id"]

        poll_resp = client.get(f"/admin/rescrape/{job_id}", headers=admin_headers)
        assert poll_resp.status_code == 200
        data = poll_resp.json()
        assert data["job_id"] == job_id
        assert data["status"] in ("queued", "running", "success", "failed")

    def test_poll_unknown_job_returns_404(self, client, admin_headers):
        resp = client.get("/admin/rescrape/nonexistent-uuid-abc123", headers=admin_headers)
        assert resp.status_code == 404

    def test_agent_cannot_trigger_rescrape(self, client, agent_headers, db_session):
        building = seed_building_with_units(db_session, "Agent Restricted Building", "Loop", [])
        resp = client.post(f"/admin/rescrape/{building.id}", headers=agent_headers)
        assert resp.status_code == 403
