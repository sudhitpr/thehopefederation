"""Role-based permission definitions."""

PERMISSIONS = {
    "Super Admin": [
        "dashboard:view",
        "registrations:view",
        "registrations:edit",
        "registrations:delete",
        "prayer_requests:view",
        "prayer_requests:edit",
        "prayer_requests:delete",
        "users:view",
        "users:create",
        "users:edit",
        "users:delete",
        "reports:view",
        "audit:view",
    ],
    "Admin": [
        "dashboard:view",
        "registrations:view",
        "registrations:edit",
        "prayer_requests:view",
        "prayer_requests:edit",
        "reports:view",
    ],
    "Staff": [
        "dashboard:view",
        "registrations:view",
        "registrations:edit",
        "prayer_requests:view",
    ],
}


def user_has_permission(user, permission_name):
    """Check if a given user object has permission."""
    if not user or not user.is_authenticated or not user.is_active:
        return False
    user_perms = PERMISSIONS.get(user.role, [])
    return permission_name in user_perms
