import pytest
from flask import url_for
from app.services.auth_service import AuthService
from app.repositories.user_repository import UserRepository
from app.repositories.audit_repository import AuditRepository


def test_auth_service_create_and_authenticate(app):
    """Test user creation, hashing, and successful authentication."""
    with app.app_context():
        auth_service = AuthService()
        user, err = auth_service.create_admin_user(
            email="admin@test.org",
            password="StrongPassword123!",
            name="Test Admin",
            role="Admin"
        )
        assert err is None
        assert user is not None
        assert user.email == "admin@test.org"
        assert user.check_password("StrongPassword123!") is True
        assert user.check_password("WrongPassword") is False

        # Authenticate
        authed_user, auth_err = auth_service.authenticate("admin@test.org", "StrongPassword123!")
        assert auth_err is None
        assert authed_user.id == user.id
        assert authed_user.last_login is not None


def test_auth_service_deactivated_user(app):
    """Test deactivated user cannot authenticate."""
    with app.app_context():
        auth_service = AuthService()
        user, _ = auth_service.create_admin_user(
            email="inactive@test.org",
            password="Password123!",
            name="Inactive Admin",
            role="Staff",
            is_active=False
        )
        authed, err = auth_service.authenticate("inactive@test.org", "Password123!")
        assert authed is None
        assert "deactivated" in err.lower()


def test_login_logout_http_flow(client, app):
    """Test full HTTP login and logout lifecycle with session cookies."""
    with app.app_context():
        auth_service = AuthService()
        auth_service.create_admin_user(
            email="login_test@example.com",
            password="SecurePassword123!",
            name="Session Tester",
            role="Admin"
        )

    # Failed login attempt
    bad_res = client.post("/admin/auth/login", data={
        "email": "login_test@example.com",
        "password": "WrongPassword"
    }, follow_redirects=True)
    assert bad_res.status_code == 401
    assert b"Invalid email address or password" in bad_res.data

    # Successful login
    good_res = client.post("/admin/auth/login", data={
        "email": "login_test@example.com",
        "password": "SecurePassword123!"
    }, follow_redirects=True)
    assert good_res.status_code == 200
    assert b"Dashboard" in good_res.data
    assert b"Session Tester" in good_res.data

    # Logout
    logout_res = client.get("/admin/auth/logout", follow_redirects=True)
    assert logout_res.status_code == 200
    assert b"signed out successfully" in logout_res.data


def test_password_reset_flow(app):
    """Test password reset token generation and completion."""
    with app.app_context():
        auth_service = AuthService()
        user, _ = auth_service.create_admin_user(
            email="reset@test.org",
            password="OldPassword123!",
            name="Reset Tester"
        )

        token = auth_service.request_password_reset("reset@test.org")
        assert token is not None

        # Reset with new password
        success, msg = auth_service.reset_password_with_token(token, "BrandNewPassword123!")
        assert success is True

        # Verify old password fails, new works
        authed_old, err_old = auth_service.authenticate("reset@test.org", "OldPassword123!")
        assert authed_old is None

        authed_new, err_new = auth_service.authenticate("reset@test.org", "BrandNewPassword123!")
        assert authed_new is not None
        assert err_new is None


def test_cli_create_superadmin(runner, app):
    """Test CLI command for creating superadmin."""
    result = runner.invoke(args=[
        "create-superadmin",
        "--email", "superadmin@example.org",
        "--password", "SuperSecret123!",
        "--name", "Head Admin"
    ])
    assert result.exit_code == 0
    assert "created successfully" in result.output

    with app.app_context():
        repo = UserRepository()
        user = repo.find_by_email("superadmin@example.org")
        assert user is not None
        assert user.role == "Super Admin"
