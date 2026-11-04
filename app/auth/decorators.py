from functools import wraps
from flask import abort, flash, redirect, url_for, request
from flask_login import current_user


def role_required(*allowed_roles):
    """
    Decorator enforcing that current_user is authenticated, active,
    and possesses one of the allowed roles.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.url))

            if not current_user.is_active:
                flash("Your administrator account is deactivated. Please contact Super Admin.", "danger")
                return redirect(url_for("auth.logout"))

            if allowed_roles and current_user.role not in allowed_roles:
                abort(403)

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def super_admin_required(fn):
    """Decorator requiring Super Admin privileges."""
    return role_required("Super Admin")(fn)


def admin_required(fn):
    """Decorator requiring either Super Admin or Admin privileges."""
    return role_required("Super Admin", "Admin")(fn)


def staff_or_above_required(fn):
    """Decorator allowing Staff, Admin, or Super Admin."""
    return role_required("Super Admin", "Admin", "Staff")(fn)
