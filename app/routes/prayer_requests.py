from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.services.prayer_request_service import PrayerRequestService
from app.repositories.prayer_request_repository import PrayerRequestRepository

prayer_requests_bp = Blueprint("prayer_requests", __name__)


@prayer_requests_bp.route("/")
@login_required
def index():
    """List prayer requests with status and category filtering."""
    status = request.args.get("status", "all")
    category = request.args.get("category", "all")
    search = request.args.get("search", "").strip()
    page = int(request.args.get("page", 1))

    service = PrayerRequestService()
    data = service.get_requests(
        page=page,
        per_page=15,
        status=status if status != "all" else None,
        category=category if category != "all" else None,
        search=search or None,
    )

    return render_template(
        "prayer_requests/index.html",
        active_page="prayer_requests",
        requests=data["items"],
        pagination=data,
        selected_status=status,
        selected_category=category,
        search_query=search,
        valid_statuses=PrayerRequestRepository.VALID_STATUSES,
        categories=PrayerRequestRepository.CATEGORIES,
    )


@prayer_requests_bp.route("/<req_id>")
@login_required
def detail(req_id):
    """View confidential prayer request details, workflow, and notes."""
    service = PrayerRequestService()
    req = service.get_by_id(req_id)
    if not req:
        flash("Prayer request not found.", "error")
        return redirect(url_for("prayer_requests.index"))

    return render_template(
        "prayer_requests/detail.html",
        active_page="prayer_requests",
        req=req,
        valid_statuses=PrayerRequestRepository.VALID_STATUSES,
    )


@prayer_requests_bp.route("/<req_id>/status", methods=["POST"])
@login_required
def update_status(req_id):
    """Update prayer request status (e.g. to in_review, praying, completed, archived)."""
    new_status = request.form.get("status", "")
    service = PrayerRequestService()
    updated, err = service.update_status(req_id, new_status, actor_user=current_user)
    if err:
        flash(err, "error")
    else:
        flash(f"Prayer request marked as '{new_status.replace('_', ' ').capitalize()}'.", "success")
    return redirect(url_for("prayer_requests.detail", req_id=req_id))


@prayer_requests_bp.route("/<req_id>/schedule", methods=["POST"])
@login_required
def schedule(req_id):
    """Assign, edit, reschedule, or clear the scheduled date and time for a prayer request."""
    action = request.form.get("action", "schedule")
    scheduled_at_raw = request.form.get("scheduled_at", "").strip()
    if not scheduled_at_raw:
        p_date = request.form.get("prayer_date", "").strip()
        p_time = request.form.get("prayer_time", "").strip()
        if p_date:
            scheduled_at_raw = f"{p_date}T{p_time or '09:00'}"

    service = PrayerRequestService()

    if action == "clear":
        updated, err = service.schedule_request(req_id, None, actor_user=current_user)
        if err:
            flash(err, "error")
        else:
            flash("Scheduled prayer session cleared.", "info")
            _flash_notification_outcome(updated)
        return redirect(url_for("prayer_requests.detail", req_id=req_id))

    if not scheduled_at_raw:
        flash("Please select a date and time to schedule the prayer request.", "error")
        return redirect(url_for("prayer_requests.detail", req_id=req_id))

    updated, err = service.schedule_request(req_id, scheduled_at_raw, actor_user=current_user)
    if err:
        flash(err, "error")
    else:
        sched_dt = updated.get("scheduled_at")
        formatted = sched_dt.strftime("%B %d, %Y at %I:%M %p") if sched_dt else scheduled_at_raw
        flash(f"Prayer request scheduled for {formatted}.", "success")
        _flash_notification_outcome(updated)
    return redirect(url_for("prayer_requests.detail", req_id=req_id))


def _flash_notification_outcome(updated):
    """Tell the admin whether the requester was emailed (the schedule itself is already saved)."""
    notification = (updated or {}).get("schedule_notification") or {}
    status = notification.get("status")
    error = notification.get("error")

    if status == "sent":
        flash("A notification email has been sent to the requester.", "success")
    elif status == "disabled":
        flash("Email notifications are currently disabled, so no email was sent.", "info")
    elif status == "skipped" and error == "no_email":
        flash("No email address is on file for this request, so no notification was sent.", "info")
    elif status in ("failed", "not_configured", "invalid_recipient"):
        flash(
            "The schedule was saved, but the notification email could not be sent. "
            "Please contact the requester directly.",
            "warning",
        )


@prayer_requests_bp.route("/<req_id>/notes", methods=["POST"])
@login_required
def add_note(req_id):
    """Add confidential internal administrative note."""
    note_text = request.form.get("note", "")
    service = PrayerRequestService()
    updated, err = service.add_admin_note(req_id, note_text, actor_user=current_user)
    if err:
        flash(err, "error")
    else:
        flash("Confidential note added successfully.", "success")
    return redirect(url_for("prayer_requests.detail", req_id=req_id))


@prayer_requests_bp.route("/<req_id>/archive", methods=["POST"])
@login_required
def archive(req_id):
    """Archive a prayer request."""
    service = PrayerRequestService()
    updated, err = service.archive_request(req_id, actor_user=current_user)
    if err:
        flash(err, "error")
    else:
        flash("Prayer request moved to archives.", "info")
    return redirect(url_for("prayer_requests.index"))


@prayer_requests_bp.route("/<req_id>/delete", methods=["POST"])
@login_required
def delete(req_id):
    """Permanently delete a prayer request (Super Admin only)."""
    service = PrayerRequestService()
    success, err = service.delete_request(req_id, actor_user=current_user)
    if not success:
        flash(err or "Unable to delete prayer request.", "error")
        return redirect(url_for("prayer_requests.detail", req_id=req_id))

    flash("Prayer request permanently deleted from database.", "success")
    return redirect(url_for("prayer_requests.index"))
