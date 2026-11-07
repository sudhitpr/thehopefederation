import secrets
from datetime import datetime, timedelta, timezone
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService


class AuthService:
    """Service handling authentication, password resets, and session management."""

    def __init__(self, user_repo=None, audit_service=None):
        self.user_repo = user_repo or UserRepository()
        self.audit_service = audit_service or AuditService()

    def authenticate(self, email, password):
        """
        Authenticate an admin user.
        Returns: (user, None) if successful, (None, error_msg) if failed.
        """
        if not email or not password:
            return None, "Email and password are required."

        user = self.user_repo.find_by_email(email)
        if not user or not user.check_password(password):
            self.audit_service.record_action(
                action="LOGIN_FAILED",
                module="AUTH",
                context={"email": email.lower().strip() if email else ""}
            )
            return None, "Invalid email address or password."

        if not user.is_active:
            self.audit_service.record_action(
                action="LOGIN_DEACTIVATED",
                module="AUTH",
                admin_user_id=user.id,
                context={"email": user.email}
            )
            return None, "Account is deactivated. Please contact Super Admin."

        # Update last login timestamp
        now = datetime.now(timezone.utc)
        self.user_repo.update(user.id, {"last_login": now})
        user.last_login = now

        self.audit_service.record_action(
            action="LOGIN_SUCCESS",
            module="AUTH",
            admin_user_id=user.id,
            context={"role": user.role}
        )
        return user, None

    def request_password_reset(self, email):
        """
        Generate password reset token.
        Returns token if user found, otherwise None (timing-safe response in controller).
        """
        if not email:
            return None

        user = self.user_repo.find_by_email(email)
        if not user or not user.is_active:
            return None

        token = secrets.token_urlsafe(32)
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        self.user_repo.update(user.id, {
            "reset_token": token,
            "reset_token_expiry": expiry
        })

        self.audit_service.record_action(
            action="PASSWORD_RESET_REQUESTED",
            module="AUTH",
            admin_user_id=user.id,
            context={"email": user.email}
        )
        return token

    def reset_password_with_token(self, token, new_password):
        """
        Reset user password using token.
        Returns (success: bool, message: str).
        """
        if not token or not new_password:
            return False, "Token and new password are required."

        if len(new_password) < 8:
            return False, "Password must be at least 8 characters long."

        user = self.user_repo.find_by_reset_token(token)
        if not user:
            return False, "Invalid or expired password reset link."

        now = datetime.now(timezone.utc)
        # Check token expiration (handle timezone-naive or aware)
        expiry = user.reset_token_expiry
        if expiry:
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if now > expiry:
                return False, "Password reset token has expired. Please request a new one."

        # Set new password
        user.set_password(new_password)
        self.user_repo.update(user.id, {
            "password_hash": user.password_hash,
            "reset_token": None,
            "reset_token_expiry": None
        })

        self.audit_service.record_action(
            action="PASSWORD_RESET_COMPLETED",
            module="AUTH",
            admin_user_id=user.id,
            context={"email": user.email}
        )
        return True, "Password has been updated successfully. Please sign in."

    def create_admin_user(self, email, password, name, role="Staff", is_active=True, created_by_id=None):
        """Create a new admin user."""
        email_clean = email.lower().strip() if email else ""
        if not email_clean or not password:
            return None, "Email and password are required."

        if self.user_repo.find_by_email(email_clean):
            return None, f"An account with email '{email_clean}' already exists."

        user = User(
            email=email_clean,
            name=name,
            role=role,
            is_active=is_active,
        )
        user.set_password(password)
        created_user = self.user_repo.create(user)

        self.audit_service.record_action(
            action="USER_CREATED",
            module="USERS",
            admin_user_id=created_by_id,
            record_id=created_user.id,
            context={"email": email_clean, "role": role}
        )
        return created_user, None
