import os
import logging
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify

from app.config import get_config
from app.extensions import login_manager
from app.database import init_db


def create_app(config_name=None):
    """Application factory for the Hope Admin Panel application."""
    app = Flask(__name__)

    # Load configuration
    config_obj = get_config(config_name)
    app.config.from_object(config_obj)

    # Configure logging
    log_level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Initialize extensions
    init_db(app)
    login_manager.init_app(app)

    # Register blueprints
    register_blueprints(app)

    # Register CLI commands
    from app.commands import register_commands
    register_commands(app)

    # Register error handlers
    register_error_handlers(app)

    # Context processors
    @app.context_processor
    def inject_global_vars():
        return {
            "current_year": datetime.now(timezone.utc).year,
            "app_name": "Hope Care Admin",
        }

    return app


def register_blueprints(app):
    """Register all modular application blueprints."""
    from app.routes.public import public_bp
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.registrations import registrations_bp
    from app.routes.prayer_requests import prayer_requests_bp
    from app.routes.users import users_bp
    from app.routes.reports import reports_bp
    from app.routes.audit import audit_bp

    app.register_blueprint(public_bp, url_prefix="/")
    app.register_blueprint(auth_bp, url_prefix="/admin/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/admin")
    app.register_blueprint(registrations_bp, url_prefix="/admin/registrations")
    app.register_blueprint(prayer_requests_bp, url_prefix="/admin/prayer-requests")
    app.register_blueprint(users_bp, url_prefix="/admin/users")
    app.register_blueprint(reports_bp, url_prefix="/admin/reports")
    app.register_blueprint(audit_bp, url_prefix="/admin/audit-logs")

    # Convenience shortcut for /admin/login
    @app.route("/admin/login")
    def admin_login_redirect():
        from flask import redirect, url_for
        return redirect(url_for("auth.login"))


def register_error_handlers(app):
    """Register centralized error handlers to prevent error leakage."""
    @app.errorhandler(403)
    def forbidden(error):
        if request.is_json:
            return jsonify({"error": "Forbidden", "message": "Access denied"}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def page_not_found(error):
        if request.is_json:
            return jsonify({"error": "Not Found", "message": "Resource not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        logging.getLogger(__name__).error("Unhandled system error: %s", error)
        if request.is_json:
            return jsonify({"error": "Internal Error", "message": "An unexpected error occurred"}), 500
        return render_template("errors/500.html"), 500
