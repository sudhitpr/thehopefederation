from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.auth.decorators import super_admin_required
from app.services.user_service import UserService
from app.models.user import User

users_bp = Blueprint("users", __name__)


@users_bp.route("/")
@login_required
@super_admin_required
def index():
    """List administrative users with role and status filtering."""
    role_filter = request.args.get("role") or None
    status_filter = request.args.get("status")
    is_active = None
    if status_filter == "active":
        is_active = True
    elif status_filter == "inactive":
        is_active = False

    page = int(request.args.get("page", 1))
    service = UserService()
    data = service.get_users_list(page=page, per_page=15, role=role_filter, is_active=is_active)

    return render_template(
        "users/index.html",
        active_page="users",
        users=data["items"],
        pagination=data,
        roles=User.ROLES,
        selected_role=role_filter,
        selected_status=status_filter,
    )


@users_bp.route("/create", methods=["GET", "POST"])
@login_required
@super_admin_required
def create():
    """Create a new administrative user."""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "Staff")
        is_active = bool(request.form.get("is_active"))

        service = UserService()
        user, err = service.create_user(
            email=email,
            password=password,
            name=name,
            role=role,
            is_active=is_active,
            actor_user=current_user,
        )

        if err:
            flash(err, "error")
            return render_template("users/create.html", roles=User.ROLES, form=request.form)

        flash(f"Administrator account for '{user.email}' created successfully.", "success")
        return redirect(url_for("users.index"))

    return render_template("users/create.html", roles=User.ROLES, form={})


@users_bp.route("/<user_id>/edit", methods=["GET", "POST"])
@login_required
@super_admin_required
def edit(user_id):
    """Edit an administrative user's details and role."""
    service = UserService()
    user = service.get_user_by_id(user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("users.index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        role = request.form.get("role", user.role)
        is_active = bool(request.form.get("is_active"))

        updated, err = service.update_user(
            user_id=user.id,
            name=name,
            role=role,
            is_active=is_active,
            actor_user=current_user,
        )

        if err:
            flash(err, "error")
            return render_template("users/edit.html", user=user, roles=User.ROLES)

        flash(f"User '{updated.email}' updated successfully.", "success")
        return redirect(url_for("users.index"))

    return render_template("users/edit.html", user=user, roles=User.ROLES)


@users_bp.route("/<user_id>/reset-password", methods=["POST"])
@login_required
@super_admin_required
def reset_password(user_id):
    """Direct password reset for an admin user by Super Admin."""
    new_password = request.form.get("new_password", "")
    service = UserService()
    success, msg = service.reset_password(user_id, new_password, actor_user=current_user)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")
    return redirect(url_for("users.edit", user_id=user_id))


@users_bp.route("/<user_id>/toggle-status", methods=["POST"])
@login_required
@super_admin_required
def toggle_status(user_id):
    """Toggle an admin user's active/deactivated status."""
    service = UserService()
    updated, err = service.toggle_active_status(user_id, actor_user=current_user)
    if err:
        flash(err, "error")
    else:
        status_label = "activated" if updated.is_active else "deactivated"
        flash(f"User '{updated.email}' has been {status_label}.", "info")
    return redirect(url_for("users.index"))


@users_bp.route("/<user_id>/delete", methods=["POST"])
@login_required
@super_admin_required
def delete(user_id):
    """Delete an administrative user."""
    service = UserService()
    success, err = service.delete_user(user_id, actor_user=current_user)
    if not success:
        flash(err or "Unable to delete user.", "error")
    else:
        flash("Administrator user deleted successfully.", "success")
    return redirect(url_for("users.index"))
