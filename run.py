import os
from dotenv import load_dotenv

# Ensure environment variables are loaded relative to project root
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
dotenv_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    load_dotenv()

from app import create_app
from app.database import get_db, create_indexes

env_name = (
    os.environ.get("FLASK_ENV")
    or os.environ.get("FLASK_CONFIG")
    or os.environ.get("ENVIRONMENT")
    or os.environ.get("ENV")
    or "development"
)

app = create_app(env_name)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = app.config.get("DEBUG", False)
    
    # Auto-initialize indexes on direct start if possible
    with app.app_context():
        try:
            create_indexes(get_db())
        except Exception as e:
            app.logger.warning(f"Could not auto-create indexes on startup: {e}")

    app.run(host="0.0.0.0", port=port, debug=debug)
