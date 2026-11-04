import pytest
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService


def test_audit_service_logging_and_filtering(app):
    """Test recording and querying audit logs."""
    with app.app_context():
        service = AuditService()
        
        # Log multiple events
        service.record_action("LOGIN_SUCCESS", "AUTH", admin_user_id="user1", context={"ip": "127.0.0.1"})
        service.record_action("USER_CREATED", "USERS", admin_user_id="user1", record_id="user2")
        service.record_action("REGISTRATION_APPROVED", "REGISTRATIONS", admin_user_id="user1", record_id="reg1")

        # Query all
        all_logs = service.get_logs(per_page=50)
        assert all_logs["total"] == 3

        # Query by module
        auth_logs = service.get_logs(module="AUTH")
        assert auth_logs["total"] == 1
        assert auth_logs["items"][0]["action"] == "LOGIN_SUCCESS"

        # Query by action
        user_logs = service.get_logs(action="USER_CREATED")
        assert user_logs["total"] == 1
        assert user_logs["items"][0]["module"] == "USERS"


def test_audit_rbac_access(client, app):
    """Verify only Super Admin can access audit logs."""
    with app.app_context():
        auth = AuthService()
        auth.create_admin_user("staff_audit@test.org", "Password123!", "Staff Audit", "Staff")
        auth.create_admin_user("super_audit@test.org", "Password123!", "Super Audit", "Super Admin")

    # Staff sign in -> 403 Forbidden
    client.post("/admin/auth/login", data={"email": "staff_audit@test.org", "password": "Password123!"})
    res_staff = client.get("/admin/audit-logs/")
    assert res_staff.status_code == 403

    # Super Admin sign in -> 200 OK
    client.get("/admin/auth/logout")
    client.post("/admin/auth/login", data={"email": "super_audit@test.org", "password": "Password123!"})
    res_super = client.get("/admin/audit-logs/")
    assert res_super.status_code == 200
    assert b"Administrative Audit Trail" in res_super.data
