import os
from unittest.mock import patch
from app.config import (
    Config,
    DevelopmentConfig,
    TestingConfig,
    ProductionConfig,
    get_config,
    get_mongo_uri,
)


def test_development_config():
    """Verify development configuration values."""
    config = get_config("development")
    assert config.DEBUG is True
    assert config.TESTING is False
    assert config.SESSION_COOKIE_HTTPONLY is True
    assert config.SESSION_COOKIE_SAMESITE == "Lax"


def test_testing_config():
    """Verify testing configuration values."""
    config = get_config("testing")
    assert config.DEBUG is False
    assert config.TESTING is True
    assert config.MONGO_DB_NAME == "hope_admin_test_db"
    assert config.WTF_CSRF_ENABLED is False


def test_production_config():
    """Verify production configuration values."""
    config = get_config("production")
    assert config.DEBUG is False
    assert config.TESTING is False
    assert config.SESSION_COOKIE_SECURE is True


def test_get_config_default_fallback():
    """Verify fallback to development config when invalid name provided."""
    config = get_config("unknown_environment")
    assert config == DevelopmentConfig


def test_get_config_aliases():
    """Verify environment name aliases like prod, dev, test."""
    assert get_config("prod") == ProductionConfig
    assert get_config("live") == ProductionConfig
    assert get_config("dev") == DevelopmentConfig
    assert get_config("test") == TestingConfig


def test_get_mongo_uri_direct():
    """Verify direct URI environment variables take priority."""
    with patch.dict(os.environ, {"DATABASE_URL": "mongodb://db.example.com:27017/my_db"}, clear=True):
        assert get_mongo_uri() == "mongodb://db.example.com:27017/my_db"


def test_get_mongo_uri_components():
    """Verify URI built from discrete host, username, password."""
    env = {
        "MONGODB_HOST": "cluster0.abc.mongodb.net",
        "MONGODB_USERNAME": "test_user",
        "MONGODB_PASSWORD": "secret_password",
        "MONGO_DB_NAME": "my_live_db",
    }
    with patch.dict(os.environ, env, clear=True):
        uri = get_mongo_uri()
        assert uri == "mongodb+srv://test_user:secret_password@cluster0.abc.mongodb.net/my_live_db?retryWrites=true&w=majority"
