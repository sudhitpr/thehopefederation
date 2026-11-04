from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Admin sign in route."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        auth_service = AuthService()
        user, err_msg = auth_service.authenticate(email, password)

        if err_msg:
            flash(err_msg, "error")
            return render_template("auth/login.html", email=email), 401

        login_user(user, remember=remember)
        flash(f"Welcome back, {user.name or user.email}!", "success")

        next_page = request.args.get("next")
        # Validate next_page to prevent open redirect vulnerabilities
        if not next_page or not next_page.startswith("/"):
            next_page = url_for("dashboard.index")
        return redirect(next_page)

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """Admin sign out route."""
    user_id = current_user.id
    email = current_user.email
    logout_user()

    audit_service = AuditService()
    audit_service.record_action(
        action="LOGOUT",
        module="AUTH",
        admin_user_id=user_id,
        context={"email": email}
    )
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Forgot password request route."""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        auth_service = AuthService()
        token = auth_service.request_password_reset(email)

        if current_app.config.get("DEBUG") and token:
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            flash(f"[Dev Mode Direct Reset Link]: {reset_url}", "info")

        flash(
            "If an active account exists for that email, a password reset link has been dispatched.",
            "success"
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Password reset completion route."""
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("auth/reset_password.html", token=token)

        auth_service = AuthService()
        success, message = auth_service.reset_password_with_token(token, password)

        if not success:
            flash(message, "error")
            return render_template("auth/reset_password.html", token=token)

        flash(message, "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)
