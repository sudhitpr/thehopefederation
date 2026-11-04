import os
from unittest.mock import patch
import pytest
from flask import Flask
from app.config import TestingConfig
from app.database.connection import get_client, get_db, init_db, reset_client, check_connection
from app.database.indexes import create_indexes
from app.commands import register_commands


@pytest.fixture(autouse=True)
def clean_client():
    """Ensure MongoDB client is reset before and after each test."""
    reset_client()
    yield
    reset_client()


def test_get_client_and_db_mongomock():
    """Test initializing MongoDB with mongomock in testing mode."""
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    app.config["USE_MONGOMOCK"] = True

    with app.app_context():
        client = get_client(app)
        assert client is not None
        db = get_db(app)
        assert db is not None
        assert db.name == "hope_admin_test_db"
        # Test basic write and read
        db.test_collection.insert_one({"name": "test_record"})
        found = db.test_collection.find_one({"name": "test_record"})
        assert found is not None
        assert found["name"] == "test_record"


def test_create_indexes_mongomock():
    """Test index creation on MongoDB collections."""
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    app.config["USE_MONGOMOCK"] = True

    with app.app_context():
        db = get_db(app)
        results = create_indexes(db)
        assert "users" in results
        assert "registrations" in results
        assert "prayer_requests" in results
        assert "audit_logs" in results

        # Verify users collection has email index
        index_info = db.users.index_information()
        assert "idx_users_email_unique" in index_info
        assert index_info["idx_users_email_unique"]["unique"] is True


def test_init_db_extension():
    """Test that init_db properly attaches client to app extensions."""
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    app.config["USE_MONGOMOCK"] = True

    init_db(app)
    assert "pymongo_client" in app.extensions
    assert "pymongo_db" in app.extensions


def test_check_connection_mongomock():
    """Test check_connection utility function with active database."""
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    app.config["USE_MONGOMOCK"] = True

    with app.app_context():
        is_healthy, latency, msg = check_connection(app)
        assert is_healthy is True
        assert latency >= 0
        assert "Connected" in msg


def test_fork_detection_reinitialization():
    """Test that process fork resets client to avoid socket sharing across workers."""
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    app.config["USE_MONGOMOCK"] = True

    with app.app_context():
        c1 = get_client(app)
        assert c1 is not None

        # Simulate PID change (as occurs after fork in Gunicorn)
        import app.database.connection as conn_mod
        original_pid = os.getpid()
        conn_mod._mongo_client_pid = original_pid + 999

        c2 = get_client(app)
        assert c2 is not None
        assert conn_mod._mongo_client_pid == original_pid


def test_check_db_cli_command():
    """Test flask check-db CLI command output."""
    app = Flask(__name__)
    app.config.from_object(TestingConfig)
    app.config["USE_MONGOMOCK"] = True
    register_commands(app)

    runner = app.test_cli_runner()
    result = runner.invoke(args=["check-db"])
    assert result.exit_code == 0
    assert "Success" in result.output
