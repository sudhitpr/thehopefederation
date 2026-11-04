from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
import logging
from app.services.registration_service import RegistrationService
from app.services.prayer_request_service import PrayerRequestService

logger = logging.getLogger(__name__)

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    """Public home/landing page (ready for designer integration)."""
    return render_template("public/index.html")


@public_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Public registration endpoint supporting both Volunteer and Partner types.
    Can be consumed as HTML Form or JSON API.
    """
    if request.method == "GET":
        return render_template("public/register.html")

    data = request.get_json(silent=True) or request.form.to_dict()
    service = RegistrationService()
    doc, err = service.create_registration(data)

    if err:
        if request.is_json:
            return jsonify({"status": "error", "message": err}), 400
        flash(err, "error")
        return render_template("public/register.html"), 400

    success_msg = f"Thank you, {doc['name']}! Your registration as a {doc['registration_type']} has been received."
    if request.is_json:
        return jsonify({"status": "success", "message": success_msg, "id": str(doc["_id"])}), 201

    flash(success_msg, "success")
    return redirect(url_for("public.register"))


@public_bp.route("/prayer-request", methods=["GET", "POST"])
def prayer_request():
    """
    Public prayer request endpoint supporting anonymous/confidential submissions.
    Can be consumed as HTML Form or JSON API.
    """
    if request.method == "GET":
        return render_template("public/prayer_request.html")

    data = request.get_json(silent=True) or request.form.to_dict()
    service = PrayerRequestService()
    doc, err = service.create_request(data)

    if err:
        if request.is_json:
            return jsonify({"status": "error", "message": err}), 400
        flash(err, "error")
        return render_template("public/prayer_request.html"), 400

    success_msg = "Your prayer request has been received with care. Our prayer team is standing with you in faith."
    if request.is_json:
        return jsonify({"status": "success", "message": success_msg, "id": str(doc["_id"])}), 201

    flash(success_msg, "success")
    return redirect(url_for("public.prayer_request"))
