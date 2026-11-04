def test_app_creation(app):
    """Verify application factory sets up testing config properly."""
    assert app.testing is True
    assert app.config["MONGO_DB_NAME"] == "hope_admin_test_db"


def test_public_routes(client):
    """Test public endpoints are operational for designer integration."""
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert b"Hope &amp; Care Community" in res_home.data or b"Hope & Care Community" in res_home.data

    res_register = client.get("/register")
    assert res_register.status_code == 200
    assert b"Community Registration" in res_register.data

    res_prayer = client.get("/prayer-request")
    assert res_prayer.status_code == 200
    assert b"Submit Prayer Request" in res_prayer.data


def test_admin_login_redirect(client):
    """Test convenience redirect from /admin/login to /admin/auth/login."""
    response = client.get("/admin/login")
    assert response.status_code == 302
    assert "/admin/auth/login" in response.headers["Location"]


def test_404_error_page(client):
    """Test custom 404 error page handles unknown routes securely."""
    response = client.get("/nonexistent-page-url")
    assert response.status_code == 404
    assert b"404 - Not Found" in response.data
