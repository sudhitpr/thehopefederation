import pytest
from app.services.auth_service import AuthService
from app.repositories.registration_repository import RegistrationRepository
from app.repositories.prayer_request_repository import PrayerRequestRepository


def test_dashboard_aggregation_service(app):
    """Test dashboard aggregation numbers for registrations and prayer requests."""
    with app.app_context():
        reg_repo = RegistrationRepository()
        prayer_repo = PrayerRequestRepository()

        # Seed registrations
        reg_repo.create({"name": "Vol 1", "email": "v1@example.com", "registration_type": "volunteer", "status": "new"})
        reg_repo.create({"name": "Vol 2", "email": "v2@example.com", "registration_type": "volunteer", "status": "approved"})
        reg_repo.create({"name": "Partner 1", "organization_name": "Org 1", "email": "p1@example.com", "registration_type": "partner", "status": "new"})

        # Seed prayer requests
        prayer_repo.create({"category": "Health & Healing", "request_text": "Healing prayer", "status": "new", "is_anonymous": False})
        prayer_repo.create({"category": "Guidance & Wisdom", "request_text": "Wisdom prayer", "status": "completed", "is_anonymous": True})

        from app.services.dashboard_service import DashboardService
        dash_service = DashboardService()
        data = dash_service.get_dashboard_data()

        assert data["registrations"]["total"] == 3
        assert data["registrations"]["volunteers"] == 2
        assert data["registrations"]["partners"] == 1
        assert data["registrations"]["new"] == 2
        assert data["registrations"]["approved"] == 1

        assert data["prayer_requests"]["total"] == 2
        assert data["prayer_requests"]["new"] == 1
        assert data["prayer_requests"]["completed"] == 1
        assert len(data["recent_registrations"]) == 3
        assert len(data["recent_prayers"]) == 2


def test_dashboard_http_auth_required(client):
    """Test unauthenticated users are redirected to login."""
    res = client.get("/admin/")
    assert res.status_code == 302
    assert "/admin/auth/login" in res.headers["Location"]
