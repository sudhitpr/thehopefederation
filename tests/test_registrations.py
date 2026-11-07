import pytest
from app.services.auth_service import AuthService
from app.services.registration_service import RegistrationService


def test_public_volunteer_registration(client, app):
    """Test public volunteer submission with valid data."""
    res = client.post("/register", data={
        "registration_type": "volunteer",
        "name": "Jane Volunteer",
        "email": "jane@example.org",
        "phone": "+1 555-0199",
        "skills": "First Aid, Logistics",
        "city": "Austin",
        "state": "TX",
        "country": "USA"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Your registration as a volunteer has been received" in res.data

    with app.app_context():
        service = RegistrationService()
        items = service.get_registrations(reg_type="volunteer")["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Jane Volunteer"
        assert items[0]["skills"] == "First Aid, Logistics"
        assert items[0]["status"] == "new"


def test_public_partner_registration(client, app):
    """Test public partner submission with valid data."""
    res = client.post("/register", data={
        "registration_type": "partner",
        "name": "Pastor David",
        "organization_name": "Grace Community Center",
        "organization_type": "Non-profit",
        "email": "david@gracecenter.org",
        "phone": "+1 555-0200",
        "website": "https://gracecenter.org",
        "city": "Dallas",
        "state": "TX"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"Your registration as a partner has been received" in res.data

    with app.app_context():
        service = RegistrationService()
        items = service.get_registrations(reg_type="partner")["items"]
        assert len(items) == 1
        assert items[0]["organization_name"] == "Grace Community Center"
        assert items[0]["registration_type"] == "partner"


def test_registration_validation_errors(client):
    """Test server-side validation catches missing and invalid data."""
    # Missing email and phone
    res1 = client.post("/register", data={
        "registration_type": "volunteer",
        "name": "Incomplete User"
    })
    assert res1.status_code == 400
    assert b"Email address is required" in res1.data

    # Partner missing organization name
    res2 = client.post("/register", data={
        "registration_type": "partner",
        "name": "Partner No Org",
        "email": "valid@email.com",
        "phone": "1234567890"
    })
    assert res2.status_code == 400
    assert b"Organization name is required" in res2.data


def test_admin_registration_management_flow(client, app):
    """Test admin filtering, status update, notes, and deletion."""
    with app.app_context():
        auth = AuthService()
        super_admin, _ = auth.create_admin_user("super_reg@test.org", "Password123!", "Super Reg", "Super Admin")
        staff, _ = auth.create_admin_user("staff_reg@test.org", "Password123!", "Staff Reg", "Staff")

        reg_service = RegistrationService()
        doc, _ = reg_service.create_registration({
            "registration_type": "volunteer",
            "name": "Sam Volunteer",
            "email": "sam@test.org",
            "phone": "555-1111",
            "status": "new"
        })
        reg_id = str(doc["_id"])

    # Login as Staff
    client.post("/admin/auth/login", data={"email": "staff_reg@test.org", "password": "Password123!"})

    # View list
    res_list = client.get("/admin/registrations/")
    assert res_list.status_code == 200
    assert b"Sam Volunteer" in res_list.data

    # View detail
    res_det = client.get(f"/admin/registrations/{reg_id}")
    assert res_det.status_code == 200
    assert b"Sam Volunteer" in res_det.data

    # Update status to approved
    res_status = client.post(f"/admin/registrations/{reg_id}/status", data={"status": "approved"}, follow_redirects=True)
    assert res_status.status_code == 200
    assert b"Status updated to" in res_status.data

    # Add admin note
    res_note = client.post(f"/admin/registrations/{reg_id}/notes", data={"note": "Interview completed successfully."}, follow_redirects=True)
    assert res_note.status_code == 200
    assert b"Interview completed successfully." in res_note.data

    # Staff attempt to delete -> should be denied
    res_del_denied = client.post(f"/admin/registrations/{reg_id}/delete", follow_redirects=True)
    assert b"Only Super Administrators can permanently delete" in res_del_denied.data

    # Switch to Super Admin
    client.get("/admin/auth/logout")
    client.post("/admin/auth/login", data={"email": "super_reg@test.org", "password": "Password123!"})

    # Super Admin deletes
    res_del = client.post(f"/admin/registrations/{reg_id}/delete", follow_redirects=True)
    assert b"permanently deleted" in res_del.data

    with app.app_context():
        assert reg_service.get_by_id(reg_id) is None
