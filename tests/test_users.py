import pytest
from app.services.auth_service import AuthService
from app.services.user_service import UserService


def test_user_service_crud(app):
    """Test full CRUD lifecycle in UserService."""
    with app.app_context():
        user_service = UserService()
        auth_service = AuthService()

        super_admin, _ = auth_service.create_admin_user(
            email="boss@example.com",
            password="Password123!",
            name="The Boss",
            role="Super Admin"
        )

        # Create user
        staff_user, err = user_service.create_user(
            email="staff1@example.com",
            password="StaffPassword123!",
            name="Staff Member",
            role="Staff",
            actor_user=super_admin
        )
        assert err is None
        assert staff_user is not None
        assert staff_user.role == "Staff"

        # Update user
        updated, err = user_service.update_user(
            user_id=staff_user.id,
            name="Senior Staff",
            role="Admin",
            is_active=True,
            actor_user=super_admin
        )
        assert err is None
        assert updated.name == "Senior Staff"
        assert updated.role == "Admin"

        # Direct password reset
        res, msg = user_service.reset_password(staff_user.id, "NewStaffPass123!", actor_user=super_admin)
        assert res is True

        # Toggle status
        toggled, _ = user_service.toggle_active_status(staff_user.id, actor_user=super_admin)
        assert toggled.is_active is False

        # Delete user
        deleted, err = user_service.delete_user(staff_user.id, actor_user=super_admin)
        assert deleted is True
        assert user_service.get_user_by_id(staff_user.id) is None


def test_prevent_self_modifications(app):
    """Verify safeguards preventing users from changing own role, deactivating, or deleting self."""
    with app.app_context():
        auth_service = AuthService()
        user_service = UserService()

        super_admin, _ = auth_service.create_admin_user(
            email="head@example.com",
            password="Password123!",
            name="Head Admin",
            role="Super Admin"
        )

        # Attempt to change own role
        _, err_role = user_service.update_user(
            user_id=super_admin.id,
            name="Head Admin",
            role="Staff",
            is_active=True,
            actor_user=super_admin
        )
        assert "cannot alter your own" in err_role

        # Attempt to deactivate self
        _, err_deact = user_service.update_user(
            user_id=super_admin.id,
            name="Head Admin",
            role="Super Admin",
            is_active=False,
            actor_user=super_admin
        )
        assert "cannot deactivate your own" in err_deact

        # Attempt to delete self
        del_res, del_err = user_service.delete_user(super_admin.id, actor_user=super_admin)
        assert del_res is False
        assert "cannot delete your own" in del_err


def test_rbac_http_restrictions(client, app):
    """Verify role-based HTTP route protection for /admin/users."""
    with app.app_context():
        auth_service = AuthService()
        auth_service.create_admin_user(
            email="staff_rbac@example.com",
            password="Password123!",
            name="Staff RBAC",
            role="Staff"
        )
        auth_service.create_admin_user(
            email="admin_rbac@example.com",
            password="Password123!",
            name="Admin RBAC",
            role="Admin"
        )
        auth_service.create_admin_user(
            email="super_rbac@example.com",
            password="Password123!",
            name="Super RBAC",
            role="Super Admin"
        )

    # 1. Staff sign-in -> Access /admin/users -> 403 Forbidden
    client.post("/admin/auth/login", data={"email": "staff_rbac@example.com", "password": "Password123!"})
    res_staff = client.get("/admin/users/")
    assert res_staff.status_code == 403

    # 2. Admin sign-in -> Access /admin/users -> 403 Forbidden
    client.get("/admin/auth/logout")
    client.post("/admin/auth/login", data={"email": "admin_rbac@example.com", "password": "Password123!"})
    res_admin = client.get("/admin/users/")
    assert res_admin.status_code == 403

    # 3. Super Admin sign-in -> Access /admin/users -> 200 OK
    client.get("/admin/auth/logout")
    client.post("/admin/auth/login", data={"email": "super_rbac@example.com", "password": "Password123!"})
    res_super = client.get("/admin/users/")
    assert res_super.status_code == 200
    assert b"System Administrators" in res_super.data
