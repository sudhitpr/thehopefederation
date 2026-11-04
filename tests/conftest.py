import pytest
from app import create_app
from app.database.connection import reset_client, get_db
from app.database.indexes import create_indexes


@pytest.fixture
def app():
    """Create and configure an isolated Flask application instance for testing."""
    reset_client()
    application = create_app("testing")
    application.config["USE_MONGOMOCK"] = True
    application.config["TESTING"] = True

    with application.app_context():
        db = get_db()
        for col_name in db.list_collection_names():
            db.drop_collection(col_name)
        create_indexes(db)
        yield application
        for col_name in db.list_collection_names():
            db.drop_collection(col_name)

    reset_client()


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test CLI runner for the app."""
    return app.test_cli_runner()


@pytest.fixture
def db(app):
    """Return test database instance."""
    with app.app_context():
        return get_db()
