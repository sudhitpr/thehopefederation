from flask import Blueprint, render_template, request
from flask_login import login_required
from app.auth.decorators import super_admin_required
from app.services.audit_service import AuditService

audit_bp = Blueprint("audit", __name__)


@audit_bp.route("/")
@login_required
@super_admin_required
def index():
    """Audit log inspection view restricted to Super Admin."""
    module_filter = request.args.get("module") or None
    action_filter = request.args.get("action") or None
    page = int(request.args.get("page", 1))

    service = AuditService()
    data = service.get_logs(
        page=page,
        per_page=25,
        module=module_filter,
        action=action_filter
    )

    modules = ["AUTH", "USERS", "REGISTRATIONS", "PRAYER_REQUESTS"]

    return render_template(
        "audit/index.html",
        active_page="audit",
        logs=data["items"],
        pagination=data,
        modules=modules,
        selected_module=module_filter,
        selected_action=action_filter,
    )
