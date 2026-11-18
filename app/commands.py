import click
from app.database import get_db, create_indexes
from app.services.auth_service import AuthService


def register_commands(app):
    """Register custom CLI commands with the Flask application."""

    @app.cli.command("init-db")
    def init_db_command():
        """Ensure database indexes are initialized."""
        with app.app_context():
            db = get_db()
            results = create_indexes(db)
            click.echo(f"Successfully initialized indexes for collections: {list(results.keys())}")

    @app.cli.command("check-db")
    def check_db_command():
        """Verify database connectivity and configuration."""
        from app.database.connection import check_connection
        with app.app_context():
            uri = app.config.get("MONGO_URI", "")
            # Redact credentials for safe display
            display_uri = uri
            if "@" in display_uri:
                prefix = display_uri.split("@")[0].split("://")[0] + "://"
                host_part = display_uri.split("@")[1]
                display_uri = f"{prefix}***:***@{host_part}"

            click.echo(f"Testing MongoDB connection ({display_uri})...")
            is_healthy, latency, msg = check_connection(app)
            if is_healthy:
                click.echo(f"Success: Connected to MongoDB in {latency} ms.")
            else:
                click.echo(f"Failed: {msg} (after {latency} ms)", err=True)

    @app.cli.command("create-superadmin")
    @click.option("--email", prompt="Admin Email", help="Super Admin Email")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Super Admin Password")
    @click.option("--name", prompt="Full Name", default="Super Administrator", help="Admin Name")
    def create_superadmin_command(email, password, name):
        """Seed or create a Super Admin user."""
        with app.app_context():
            auth_service = AuthService()
            user, err = auth_service.create_admin_user(
                email=email,
                password=password,
                name=name,
                role="Super Admin",
                is_active=True
            )
            if err:
                click.echo(f"Error: {err}", err=True)
            else:
                click.echo(f"Super Admin user '{user.email}' created successfully.")

    @app.cli.command("send-test-email")
    @click.option("--to", "recipient", required=True, help="Address that should receive the test email")
    def send_test_email_command(recipient):
        """Verify SMTP settings by sending a test email (credentials are never printed)."""
        from app.services.email_service import EmailService
        with app.app_context():
            cfg = app.config
            mode = "SSL" if cfg.get("MAIL_USE_SSL") else ("STARTTLS" if cfg.get("MAIL_USE_TLS") else "PLAIN")
            click.echo(
                f"Mail settings: enabled={bool(cfg.get('MAIL_ENABLED'))}, "
                f"server={cfg.get('MAIL_SERVER') or '(not set)'}:{cfg.get('MAIL_PORT')} ({mode}), "
                f"sender={cfg.get('MAIL_DEFAULT_SENDER') or '(not set)'}, "
                f"password={'set' if cfg.get('MAIL_PASSWORD') else 'NOT SET'}"
            )
            if not cfg.get("MAIL_ENABLED"):
                click.echo("MAIL_ENABLED is off; set MAIL_ENABLED=true to send.", err=True)
                return

            service = EmailService(cfg)
            result = service.send(
                recipient,
                f"Test email - {cfg.get('MAIL_SENDER_NAME') or 'Hope Admin'}",
                "This is a test email confirming that SMTP is configured correctly for the Hope admin portal.",
            )
            if result.sent:
                click.echo("Success: test email sent.")
            else:
                click.echo(f"Failed: {result.status} ({result.error}). See application log for details.", err=True)

    @app.cli.command("send-prayer-reminders")
    @click.option("--dry-run", is_flag=True, default=False, help="Check upcoming requests without sending emails.")
    @click.option("--window-minutes", type=int, default=None, help="Lookahead window in minutes (default: 60).")
    def send_prayer_reminders_command(dry_run, window_minutes):
        """Run the upcoming prayer request email reminder check."""
        from app.services.prayer_reminder_service import PrayerReminderService
        with app.app_context():
            summary = PrayerReminderService().run(window_minutes=window_minutes, dry_run=dry_run)
            click.echo(
                f"Status: {summary['status']} | Window: {summary['window_start']} .. {summary['window_end']} "
                f"({summary['timezone']}) | Found: {summary['found']} | Pending: {summary['pending']} | "
                f"Sent: {summary['sent']} | Failed: {summary['failed']} | Skipped: {summary['skipped']}"
            )
            if summary["status"] == "db_error":
                raise SystemExit(1)
