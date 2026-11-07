from flask import Blueprint, render_template
from flask_login import login_required
from app.services.dashboard_service import DashboardService

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    """Main administrative dashboard displaying summary metrics and recent activity."""
    service = DashboardService()
    data = service.get_dashboard_data()
    return render_template("dashboard/index.html", active_page="dashboard", data=data)
