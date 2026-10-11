import pytest
import mongomock
from bson import ObjectId
from app import create_app

@pytest.fixture
def client(monkeypatch):
    mock_client = mongomock.MongoClient()
    monkeypatch.setattr("app.db.get_mongo_client", lambda uri=None: mock_client)
    app = create_app("testing")
    with app.test_client() as client:
        yield client

def test_healthz_endpoint(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["status"] == "ok"
    assert json_data["db"] is True

def test_check_availability(client):
    res = client.get("/api/auth/check?username=available_user")
    assert res.status_code == 200
    assert res.get_json()["data"]["available"] is True

def test_public_pages(client):
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert b"Mail Shield" in res_home.data

    res_privacy = client.get("/privacy")
    assert res_privacy.status_code == 200

    res_terms = client.get("/terms")
    assert res_terms.status_code == 200

def test_auth_and_manual_scan_workflow(client):
    # 1. Signup
    signup_res = client.post("/api/auth/signup", json={
        "username": "tester",
        "email": "tester@example.com",
        "password": "SecurePass123!",
        "accept": True
    })
    assert signup_res.status_code in (200, 201)
    assert signup_res.get_json()["ok"] is True

    # 2. Manual Scan API
    scan_res = client.post("/api/scan/manual", json={
        "from_name": "Security Team",
        "from_address": "support@paypal-security-update.com",
        "reply_to": "attacker@darkweb.org",
        "subject": "URGENT: Verify your account immediately",
        "body": "Your account has been suspended! Click http://192.168.1.1/login to verify your password.",
        "urls": ["http://192.168.1.1/login"],
        "attachments": ["statement.pdf.exe"],
        "save": True
    })
    assert scan_res.status_code == 200
    scan_data = scan_res.get_json()
    assert scan_data["ok"] is True
    assert scan_data["data"]["score"] > 50
    assert scan_data["data"]["label"] in ("suspicious", "spam")
    assert len(scan_data["data"]["reasons"]) > 0

    # 3. Rules API
    rules_res = client.get("/api/rules")
    assert rules_res.status_code == 200
    assert rules_res.get_json()["ok"] is True

    # 4. Account Profile API
    acct_res = client.get("/api/account")
    assert acct_res.status_code == 200
    assert acct_res.get_json()["data"]["username"] == "tester"

    patch_res = client.patch("/api/account/profile", json={"display_name": "Test User"})
    assert patch_res.status_code == 200
    assert patch_res.get_json()["ok"] is True

    # 5. User Settings API
    settings_res = client.get("/api/settings")
    assert settings_res.status_code == 200
    assert settings_res.get_json()["ok"] is True

    # 6. Cache Stats API
    cache_res = client.get("/api/mail/cache/stats")
    assert cache_res.status_code == 200
    cache_data = cache_res.get_json()
    assert cache_data["ok"] is True
    assert "percent" in cache_data["data"]
    assert "used_formatted" in cache_data["data"]

def test_system_health_page_and_api(client):
    res_page = client.get("/system-health")
    assert res_page.status_code == 200
    assert b"System Health" in res_page.data

    res_api = client.get("/api/system-health/status")
    assert res_api.status_code == 200
    json_data = res_api.get_json()
    assert json_data["ok"] is True
    assert "services" in json_data
    assert "engine" in json_data["services"]
    assert json_data["services"]["engine"]["status"] == "operational"

