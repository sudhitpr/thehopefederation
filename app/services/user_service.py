import logging
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class UserService:
    """Service handling administrative user management and RBAC rules."""

    def __init__(self, user_repo=None, audit_service=None):
        self.user_repo = user_repo or UserRepository()
        self.audit_service = audit_service or AuditService()

    def get_users_list(self, page=1, per_page=15, role=None, is_active=None):
        """Get paginated list of admin users."""
        skip = (page - 1) * per_page
        users = self.user_repo.list_all(skip=skip, limit=per_page, role=role, is_active=is_active)
        total = self.user_repo.count(role=role, is_active=is_active)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        return {
            "items": users,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }

    def get_user_by_id(self, user_id):
        """Retrieve user by ID."""
        return self.user_repo.find_by_id(user_id)

    def create_user(self, email, password, name, role="Staff", is_active=True, actor_user=None):
        """Create a new admin user."""
        email_clean = email.lower().strip() if email else ""
        if not email_clean or not password:
            return None, "Email and password are required."

        if len(password) < 8:
            return None, "Password must be at least 8 characters long."

        if role not in User.ROLES:
            return None, f"Invalid role '{role}'. Allowed roles: {', '.join(User.ROLES)}"

        if self.user_repo.find_by_email(email_clean):
            return None, f"User with email '{email_clean}' already exists."

        user = User(
            email=email_clean,
            name=name.strip() if name else "",
            role=role,
            is_active=is_active,
        )
        user.set_password(password)
        created_user = self.user_repo.create(user)

        actor_id = actor_user.id if actor_user else None
        self.audit_service.record_action(
            action="ADMIN_USER_CREATED",
            module="USERS",
            admin_user_id=actor_id,
            record_id=created_user.id,
            context={"email": created_user.email, "role": created_user.role}
        )
        return created_user, None

    def update_user(self, user_id, name, role, is_active, actor_user):
        """
        Update user profile, role, and active status.
        Enforces self-protection: users cannot change their own role or deactivate themselves.
        """
        user = self.user_repo.find_by_id(user_id)
        if not user:
            return None, "User not found."

        if role not in User.ROLES:
            return None, f"Invalid role '{role}'."

        # Guard: cannot change own role
        if actor_user and actor_user.id == user.id and user.role != role:
            return None, "You cannot alter your own administrative role."

        # Guard: cannot deactivate oneself
        if actor_user and actor_user.id == user.id and not is_active:
            return None, "You cannot deactivate your own account."

        # Check role change for audit
        role_changed = user.role != role
        old_role = user.role

        updates = {
            "name": name.strip() if name else "",
            "role": role,
            "is_active": bool(is_active),
        }
        updated_user = self.user_repo.update(user.id, updates)

        actor_id = actor_user.id if actor_user else None
        self.audit_service.record_action(
            action="ADMIN_USER_UPDATED",
            module="USERS",
            admin_user_id=actor_id,
            record_id=user.id,
            context={"email": user.email, "role": role, "is_active": is_active}
        )

        if role_changed:
            self.audit_service.record_action(
                action="ADMIN_ROLE_CHANGED",
                module="USERS",
                admin_user_id=actor_id,
                record_id=user.id,
                context={"old_role": old_role, "new_role": role, "email": user.email}
            )

        return updated_user, None

    def reset_password(self, user_id, new_password, actor_user):
        """Super admin resetting a user's password directly."""
        if not new_password or len(new_password) < 8:
            return False, "Password must be at least 8 characters long."

        user = self.user_repo.find_by_id(user_id)
        if not user:
            return False, "User not found."

        user.set_password(new_password)
        self.user_repo.update(user.id, {
            "password_hash": user.password_hash,
            "reset_token": None,
            "reset_token_expiry": None
        })

        actor_id = actor_user.id if actor_user else None
        self.audit_service.record_action(
            action="ADMIN_PASSWORD_RESET_BY_ADMIN",
            module="USERS",
            admin_user_id=actor_id,
            record_id=user.id,
            context={"email": user.email}
        )
        return True, "Password has been successfully updated."

    def toggle_active_status(self, user_id, actor_user):
        """Toggle active/inactive status."""
        user = self.user_repo.find_by_id(user_id)
        if not user:
            return None, "User not found."

        if actor_user and actor_user.id == user.id:
            return None, "You cannot deactivate your own account."

        new_status = not user.is_active
        updated = self.user_repo.update(user.id, {"is_active": new_status})

        actor_id = actor_user.id if actor_user else None
        self.audit_service.record_action(
            action="ADMIN_USER_ACTIVATED" if new_status else "ADMIN_USER_DEACTIVATED",
            module="USERS",
            admin_user_id=actor_id,
            record_id=user.id,
            context={"email": user.email, "is_active": new_status}
        )
        return updated, None

    def delete_user(self, user_id, actor_user):
        """Permanently delete admin user (Super Admin only)."""
        user = self.user_repo.find_by_id(user_id)
        if not user:
            return False, "User not found."

        if actor_user and actor_user.id == user.id:
            return False, "You cannot delete your own account."

        success = self.user_repo.delete(user.id)
        if success:
            actor_id = actor_user.id if actor_user else None
            self.audit_service.record_action(
                action="ADMIN_USER_DELETED",
                module="USERS",
                admin_user_id=actor_id,
                record_id=user.id,
                context={"email": user.email, "role": user.role}
            )
        return success, None
