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
