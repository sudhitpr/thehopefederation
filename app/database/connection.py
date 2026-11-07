import os
import time
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, PyMongoError
from flask import current_app, g

logger = logging.getLogger(__name__)

_mongo_client = None
_mongo_client_pid = None


def get_client(app=None):
    """
    Get or initialize the MongoDB client.
    Guarantees process fork safety and thread-safe connection pooling.
    """
    global _mongo_client, _mongo_client_pid
    current_pid = os.getpid()

    # If the process was forked (e.g., Gunicorn prefork workers), discard the parent client
    if _mongo_client is not None:
        if _mongo_client_pid == current_pid:
            return _mongo_client
        else:
            logger.info("Process fork detected (PID changed from %s to %s). Reinitializing MongoDB client.", _mongo_client_pid, current_pid)
            try:
                _mongo_client.close()
            except Exception:
                pass
            _mongo_client = None
            _mongo_client_pid = None

    if app is None:
        if current_app:
            app = current_app._get_current_object()
        else:
            raise RuntimeError("Application context or app instance is required to initialize MongoDB client.")

    is_testing = app.config.get("TESTING", False)
    use_mock = app.config.get("USE_MONGOMOCK", False)

    if is_testing and use_mock:
        import mongomock
        logger.info("Initializing mongomock client for testing.")
        _mongo_client = mongomock.MongoClient()
        _mongo_client_pid = current_pid
        return _mongo_client

    mongo_uri = app.config.get("MONGO_URI")
    if not mongo_uri:
        from app.config import get_mongo_uri
        mongo_uri = get_mongo_uri()

    if not mongo_uri:
        if is_testing or app.config.get("DEBUG", False):
            mongo_uri = "mongodb://localhost:27017/"
        else:
            raise RuntimeError(
                "MongoDB connection URI is not configured for production environment. "
                "Please configure the MONGO_URI or MONGODB_URI environment variable."
            )

    # Sanitize and strip surrounding quotes if any
    mongo_uri = mongo_uri.strip().strip('"').strip("'")

    # Guard against accidental localhost in production
    is_production = not app.config.get("DEBUG", False) and not is_testing
    if is_production and ("localhost" in mongo_uri or "127.0.0.1" in mongo_uri):
        from app.config import get_mongo_uri
        alt_uri = get_mongo_uri()
        if alt_uri and "localhost" not in alt_uri and "127.0.0.1" not in alt_uri:
            mongo_uri = alt_uri.strip().strip('"').strip("'")
            logger.warning("Overriding localhost URI in production with live database URI from environment.")
        else:
            logger.warning("Production configuration is currently pointing to a local MongoDB address (%s).", mongo_uri)

    # Pool & timeout settings
    server_timeout = int(app.config.get("MONGO_SERVER_SELECTION_TIMEOUT_MS") or os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", 5000))
    connect_timeout = int(app.config.get("MONGO_CONNECT_TIMEOUT_MS") or os.environ.get("MONGO_CONNECT_TIMEOUT_MS", 5000))
    socket_timeout = int(app.config.get("MONGO_SOCKET_TIMEOUT_MS") or os.environ.get("MONGO_SOCKET_TIMEOUT_MS", 10000))
    max_pool_size = int(app.config.get("MONGO_MAX_POOL_SIZE") or os.environ.get("MONGO_MAX_POOL_SIZE", 50))
    min_pool_size = int(app.config.get("MONGO_MIN_POOL_SIZE") or os.environ.get("MONGO_MIN_POOL_SIZE", 0))

    client_kwargs = {
        "serverSelectionTimeoutMS": server_timeout,
        "connectTimeoutMS": connect_timeout,
        "socketTimeoutMS": socket_timeout,
        "maxPoolSize": max_pool_size,
        "minPoolSize": min_pool_size,
        "maxIdleTimeMS": 60000,
        "retryWrites": True,
    }

    # Automatically resolve CA bundle for TLS/Atlas connections if not explicitly provided
    ca_file = app.config.get("MONGO_TLS_CA_FILE") or os.environ.get("SSL_CERT_FILE")
    if not ca_file and ("+srv" in mongo_uri or "ssl=true" in mongo_uri.lower() or "tls=true" in mongo_uri.lower()):
        try:
            import certifi
            ca_file = certifi.where()
        except ImportError:
            for candidate in [
                "/etc/ssl/cert.pem",
                "/etc/ssl/certs/ca-certificates.crt",
                "/etc/pki/tls/certs/ca-bundle.crt",
                "/etc/ssl/ca-bundle.pem",
            ]:
                if os.path.exists(candidate):
                    ca_file = candidate
                    break

    if ca_file:
        client_kwargs["tlsCAFile"] = ca_file

    new_client = None
    try:
        new_client = MongoClient(mongo_uri, **client_kwargs)
        # Verify connection responsiveness
        new_client.admin.command("ping")
        _mongo_client = new_client
        _mongo_client_pid = current_pid
        logger.info("MongoDB client connected and pinged successfully.")
        return _mongo_client
    except (ConnectionFailure, ServerSelectionTimeoutError) as err:
        logger.error("Failed to connect to MongoDB: %s", err)
        if new_client is not None:
            try:
                new_client.close()
            except Exception:
                pass
        _mongo_client = None
        _mongo_client_pid = None
        raise


def get_db(app=None):
    """
    Return the active MongoDB database instance.
    Reuses connection from Flask context 'g' or application extensions.
    """
    if "db" in g:
        return g.db

    target_app = app
    if target_app is None and current_app:
        target_app = current_app._get_current_object()

    if target_app and hasattr(target_app, "extensions") and "pymongo_db" in target_app.extensions:
        # Check fork safety for existing client
        global _mongo_client_pid
        if _mongo_client_pid == os.getpid():
            db = target_app.extensions["pymongo_db"]
            if current_app:
                g.db = db
            return db

    client = get_client(target_app)
    if target_app is None:
        if current_app:
            target_app = current_app._get_current_object()
        else:
            raise RuntimeError("Application context or app instance required to retrieve database.")

    db_name = target_app.config.get("MONGO_DB_NAME", "hope_admin_db")
    db = client[db_name]
    
    if hasattr(target_app, "extensions"):
        target_app.extensions["pymongo_client"] = client
        target_app.extensions["pymongo_db"] = db

    if current_app:
        g.db = db
    return db


def close_db(e=None):
    """Teardown handler to remove db from request context."""
    g.pop("db", None)


def init_db(app):
    """Initialize database extension with the Flask app."""
    app.extensions = getattr(app, "extensions", {})
    
    with app.app_context():
        try:
            client = get_client(app)
            db_name = app.config.get("MONGO_DB_NAME", "hope_admin_db")
            db = client[db_name]
            app.extensions["pymongo_client"] = client
            app.extensions["pymongo_db"] = db
        except Exception as err:
            logger.warning("MongoDB initial connection deferred or failed during init_db: %s", err)

    app.teardown_appcontext(close_db)


def check_connection(app=None):
    """
    Check MongoDB connectivity and measure round-trip latency.
    Returns: (is_healthy: bool, latency_ms: float, message: str)
    """
    start_time = time.perf_counter()
    try:
        db = get_db(app)
        db.command("ping")
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return True, elapsed_ms, "Connected successfully"
    except PyMongoError as err:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return False, elapsed_ms, str(err)
    except Exception as err:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return False, elapsed_ms, str(err)


def reset_client():
    """Reset the global MongoDB client (primarily for testing and worker recycle)."""
    global _mongo_client, _mongo_client_pid
    if _mongo_client is not None:
        try:
            _mongo_client.close()
        except Exception:
            pass
        _mongo_client = None
    _mongo_client_pid = None
