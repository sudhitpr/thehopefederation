import os
import urllib.parse
from datetime import timedelta
from dotenv import load_dotenv

# Ensure .env is reliably loaded regardless of current working directory
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
dotenv_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    load_dotenv()


def get_mongo_uri():
    """
    Resolve the MongoDB connection URI from environment variables.
    Supports standard full URIs as well as individual component variables
    (host, port, username, password, db_name).
    """
    # 1. Direct full connection URI options
    for env_var in [
        "MONGODB_URI",
        "MONGO_URI",
        "DATABASE_URL",
        "MONGODB_URL",
        "MONGO_URL",
    ]:
        val = os.environ.get(env_var)
        if val and val.strip():
            clean_val = val.strip().strip('"').strip("'")
            if clean_val:
                return clean_val

    # 2. Build URI from discrete components if host/cluster is provided
    host = (
        os.environ.get("MONGODB_HOST")
        or os.environ.get("MONGO_HOST")
        or os.environ.get("MONGODB_SERVER")
        or os.environ.get("MONGO_SERVER")
        or os.environ.get("MONGODB_CLUSTER")
    )
    if host:
        host = host.strip().strip('"').strip("'")
        user = (
            os.environ.get("MONGODB_USERNAME")
            or os.environ.get("MONGODB_USER")
            or os.environ.get("MONGO_USER")
            or ""
        )
        password = (
            os.environ.get("MONGODB_PASSWORD")
            or os.environ.get("MONGO_PASSWORD")
            or os.environ.get("MONGO_PASS")
            or ""
        )
        db_name = (
            os.environ.get("MONGO_DB_NAME")
            or os.environ.get("MONGODB_DATABASE")
            or os.environ.get("MONGO_DATABASE")
            or "hope_admin_db"
        )
        port = os.environ.get("MONGODB_PORT") or os.environ.get("MONGO_PORT")

        auth_part = ""
        if user:
            user_clean = urllib.parse.quote_plus(user.strip().strip('"').strip("'"))
            if password:
                pass_clean = urllib.parse.quote_plus(password.strip().strip('"').strip("'"))
                auth_part = f"{user_clean}:{pass_clean}@"
            else:
                auth_part = f"{user_clean}@"

        if host.startswith("mongodb://") or host.startswith("mongodb+srv://"):
            return host

        is_srv = "mongodb.net" in host or os.environ.get("MONGODB_SRV", "").lower() in ("true", "1", "yes")
        if is_srv:
            return f"mongodb+srv://{auth_part}{host}/{db_name}?retryWrites=true&w=majority"
        else:
            port_str = f":{port}" if port else ":27017"
            return f"mongodb://{auth_part}{host}{port_str}/{db_name}"

    return None


class Config:
    """Base configuration with sensible defaults."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    MONGODB_USERNAME = (
        os.environ.get("MONGODB_USERNAME")
        or os.environ.get("MONGODB_USER")
        or os.environ.get("MONGO_USER")
    )
    MONGODB_PASSWORD = (
        os.environ.get("MONGODB_PASSWORD")
        or os.environ.get("MONGO_PASSWORD")
        or os.environ.get("MONGO_PASS")
    )
    MONGO_DB_NAME = (
        os.environ.get("MONGO_DB_NAME")
        or os.environ.get("MONGODB_DATABASE")
        or os.environ.get("MONGO_DATABASE")
        or "hope_admin_db"
    )
    
    # Resolved connection URI with fallback
    MONGO_URI = get_mongo_uri() or "mongodb://localhost:27017/"

    # Connection pooling & performance settings
    MONGO_MAX_POOL_SIZE = int(os.environ.get("MONGO_MAX_POOL_SIZE", 50))
    MONGO_MIN_POOL_SIZE = int(os.environ.get("MONGO_MIN_POOL_SIZE", 0))
    MONGO_SERVER_SELECTION_TIMEOUT_MS = int(os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", 5000))
    MONGO_CONNECT_TIMEOUT_MS = int(os.environ.get("MONGO_CONNECT_TIMEOUT_MS", 5000))
    MONGO_SOCKET_TIMEOUT_MS = int(os.environ.get("MONGO_SOCKET_TIMEOUT_MS", 10000))
    MONGO_TLS_CA_FILE = os.environ.get("MONGO_TLS_CA_FILE") or os.environ.get("SSL_CERT_FILE")

    # Session security
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(os.environ.get("ADMIN_SESSION_LIFETIME_HOURS", "12"))
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False

    # Pagination & display
    ITEMS_PER_PAGE = int(os.environ.get("ITEMS_PER_PAGE", "15"))

    # Security settings
    WTF_CSRF_TIME_LIMIT = 3600


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False


class TestingConfig(Config):
    """Testing environment configuration."""
    DEBUG = False
    TESTING = True
    MONGO_DB_NAME = os.environ.get("TEST_MONGO_DB_NAME", "hope_admin_test_db")
    SECRET_KEY = "test-secret-key-never-use-in-production"
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() in ("true", "1", "yes")
    SEND_FILE_MAX_AGE_DEFAULT = int(os.environ.get("STATIC_MAX_AGE", 43200))

    # In production, require live database URI instead of falling back to localhost
    _resolved_uri = get_mongo_uri()
    MONGO_URI = _resolved_uri if _resolved_uri else os.environ.get("MONGO_URI", "")


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(config_name=None):
    """Retrieve config class based on env name or environment variables."""
    if not config_name:
        config_name = (
            os.environ.get("FLASK_ENV")
            or os.environ.get("FLASK_CONFIG")
            or os.environ.get("ENVIRONMENT")
            or os.environ.get("ENV")
            or "development"
        )
    name = str(config_name).lower().strip()
    if name in ("prod", "production", "live"):
        return ProductionConfig
    elif name in ("dev", "development", "local"):
        return DevelopmentConfig
    elif name in ("test", "testing"):
        return TestingConfig

    return config_by_name.get(name, DevelopmentConfig)
