from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.services.registration_service import RegistrationService
from app.repositories.registration_repository import RegistrationRepository

registrations_bp = Blueprint("registrations", __name__)


@registrations_bp.route("/")
@login_required
def index():
    """List registrations with filtering by type, status, search, and date."""
    reg_type = request.args.get("type", "all")
    status = request.args.get("status", "all")
    search = request.args.get("search", "").strip()
    page = int(request.args.get("page", 1))

    service = RegistrationService()
    data = service.get_registrations(
        page=page,
        per_page=15,
        reg_type=reg_type if reg_type != "all" else None,
        status=status if status != "all" else None,
        search=search or None,
    )

    return render_template(
        "registrations/index.html",
        active_page="registrations",
        registrations=data["items"],
        pagination=data,
        selected_type=reg_type,
        selected_status=status,
        search_query=search,
        valid_statuses=RegistrationRepository.VALID_STATUSES,
    )


@registrations_bp.route("/<reg_id>")
@login_required
def detail(reg_id):
    """View full details of a volunteer or partner registration."""
    service = RegistrationService()
    reg = service.get_by_id(reg_id)
    if not reg:
        flash("Registration record not found.", "error")
        return redirect(url_for("registrations.index"))

    return render_template(
        "registrations/detail.html",
        active_page="registrations",
        reg=reg,
        valid_statuses=RegistrationRepository.VALID_STATUSES,
    )


@registrations_bp.route("/<reg_id>/status", methods=["POST"])
@login_required
def update_status(reg_id):
    """Update registration status."""
    new_status = request.form.get("status", "")
    service = RegistrationService()
    updated, err = service.update_status(reg_id, new_status, actor_user=current_user)
    if err:
        flash(err, "error")
    else:
        flash(f"Status updated to '{new_status.capitalize()}'.", "success")
    return redirect(url_for("registrations.detail", reg_id=reg_id))


@registrations_bp.route("/<reg_id>/notes", methods=["POST"])
@login_required
def add_note(reg_id):
    """Add an internal administrative note."""
    note_text = request.form.get("note", "")
    service = RegistrationService()
    updated, err = service.add_admin_note(reg_id, note_text, actor_user=current_user)
    if err:
        flash(err, "error")
    else:
        flash("Note recorded successfully.", "success")
    return redirect(url_for("registrations.detail", reg_id=reg_id))


@registrations_bp.route("/<reg_id>/delete", methods=["POST"])
@login_required
def delete(reg_id):
    """Delete a registration record (Super Admin only)."""
    service = RegistrationService()
    success, err = service.delete_registration(reg_id, actor_user=current_user)
    if not success:
        flash(err or "Unable to delete registration.", "error")
        return redirect(url_for("registrations.detail", reg_id=reg_id))

    flash("Registration record permanently deleted.", "success")
    return redirect(url_for("registrations.index"))
