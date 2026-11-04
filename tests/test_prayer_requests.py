import pytest
from app.services.auth_service import AuthService
from app.services.prayer_request_service import PrayerRequestService


def test_public_prayer_request_submission(client, app):
    """Test public submission of a standard prayer request."""
    res = client.post("/prayer-request", data={
        "name": "Sarah Connor",
        "email": "sarah@example.org",
        "phone": "+1 555-4321",
        "category": "Health & Healing",
        "request_text": "Please pray for my mother recovering from surgery.",
        "preferred_contact": "Email"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Your prayer request has been received with care" in res.data

    with app.app_context():
        service = PrayerRequestService()
        items = service.get_requests(category="Health & Healing")["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Sarah Connor"
        assert items[0]["is_anonymous"] is False
        assert items[0]["status"] == "new"


def test_anonymous_prayer_request_submission(client, app):
    """Test public submission of an anonymous prayer request strips contact information."""
    res = client.post("/prayer-request", data={
        "name": "Should Be Hidden",
        "email": "hidden@example.com",
        "category": "Financial & Provision",
        "request_text": "Seeking wisdom during a difficult job transition.",
        "is_anonymous": "true"
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        service = PrayerRequestService()
        items = service.get_requests(category="Financial & Provision")["items"]
        assert len(items) == 1
        assert items[0]["is_anonymous"] is True
        assert items[0]["name"] == "Anonymous"
        assert items[0]["email"] == ""


def test_prayer_request_validation(client):
    """Test validation catches missing prayer text."""
    res = client.post("/prayer-request", data={
        "name": "Someone",
        "category": "Other",
        "request_text": "   "  # whitespace only
    })
    assert res.status_code == 400
    assert b"content cannot be empty" in res.data


def test_admin_prayer_request_flow(client, app):
    """Test admin review workflow: status updates, notes, archive, and deletion."""
    with app.app_context():
        auth = AuthService()
        super_admin, _ = auth.create_admin_user("super_pr@test.org", "Password123!", "Super PR", "Super Admin")
        staff, _ = auth.create_admin_user("staff_pr@test.org", "Password123!", "Staff PR", "Staff")

        prayer_service = PrayerRequestService()
        doc, _ = prayer_service.create_request({
            "category": "Guidance & Wisdom",
            "request_text": "Pray for guidance on leadership transition.",
            "name": "Elder John",
            "status": "new"
        })
        req_id = str(doc["_id"])

    # Staff sign in
    client.post("/admin/auth/login", data={"email": "staff_pr@test.org", "password": "Password123!"})

    # Access listing
    res_list = client.get("/admin/prayer-requests/")
    assert res_list.status_code == 200
    assert b"Guidance &amp; Wisdom" in res_list.data or b"Guidance & Wisdom" in res_list.data

    # Access detail
    res_detail = client.get(f"/admin/prayer-requests/{req_id}")
    assert res_detail.status_code == 200
    assert b"Elder John" in res_detail.data
    assert b"leadership transition" in res_detail.data

    # Update status to 'praying'
    res_status = client.post(f"/admin/prayer-requests/{req_id}/status", data={"status": "praying"}, follow_redirects=True)
    assert res_status.status_code == 200
    assert b"marked as" in res_status.data and b"Praying" in res_status.data

    # Add pastoral note
    res_note = client.post(f"/admin/prayer-requests/{req_id}/notes", data={"note": "Assigned to Tuesday intercession team."}, follow_redirects=True)
    assert res_note.status_code == 200
    assert b"Assigned to Tuesday intercession team." in res_note.data

    # Archive
    res_arch = client.post(f"/admin/prayer-requests/{req_id}/archive", follow_redirects=True)
    assert res_arch.status_code == 200
    assert b"moved to archives" in res_arch.data

    # Staff attempt to delete -> rejected
    res_staff_del = client.post(f"/admin/prayer-requests/{req_id}/delete", follow_redirects=True)
    assert b"Only Super Administrators can permanently delete" in res_staff_del.data

    # Super admin deletes
    client.get("/admin/auth/logout")
    client.post("/admin/auth/login", data={"email": "super_pr@test.org", "password": "Password123!"})
    res_super_del = client.post(f"/admin/prayer-requests/{req_id}/delete", follow_redirects=True)
    assert b"permanently deleted" in res_super_del.data

    with app.app_context():
        assert prayer_service.get_by_id(req_id) is None
