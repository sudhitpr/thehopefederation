from flask import Blueprint, render_template, request
from flask_login import login_required
from app.services.report_service import ReportService

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/")
@login_required
def index():
    """Reports and metrics breakdown dashboard with date presets."""
    period = request.args.get("period", "all")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    service = ReportService()
    report = service.generate_report(period=period, custom_start=start_date, custom_end=end_date)

    return render_template(
        "reports/index.html",
        active_page="reports",
        report=report,
        selected_period=period,
        custom_start=start_date,
        custom_end=end_date,
    )
