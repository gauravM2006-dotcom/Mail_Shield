import pytest
import mongomock
from bson import ObjectId
from app import create_app
from app.db import get_mongo_client
from app.auth.services import register_user, authenticate_user, is_valid_password

@pytest.fixture
def app_with_mock_db(monkeypatch):
    mock_client = mongomock.MongoClient()
    monkeypatch.setattr("app.db.get_mongo_client", lambda uri=None: mock_client)
    monkeypatch.setattr("app.auth.services.users_col", lambda: mock_client["mailshield"]["users"])
    monkeypatch.setattr("app.auth.services.auth_tokens_col", lambda: mock_client["mailshield"]["auth_tokens"])
    monkeypatch.setattr("app.auth.services.user_settings_col", lambda: mock_client["mailshield"]["user_settings"])
    monkeypatch.setattr("app.auth.services.rule_configs_col", lambda: mock_client["mailshield"]["rule_configs"])
    monkeypatch.setattr("app.auth.services.audit_logs_col", lambda: mock_client["mailshield"]["audit_logs"])
    
    app = create_app("testing")
    return app

def test_password_policy():
    assert is_valid_password("Short1!") is False
    assert is_valid_password("nouppercase1!") is False
    assert is_valid_password("NOLOWERCASE1!") is False
    assert is_valid_password("NoNumberHere!") is False
    assert is_valid_password("NoSymbol1234") is False
    assert is_valid_password("ValidPassword123!") is True

def test_user_registration_and_authentication(app_with_mock_db):
    with app_with_mock_db.app_context():
        # Register user
        user, err = register_user("testuser", "test@example.com", "SecurePass123!")
        assert err is None
        assert user is not None
        assert user.username == "testuser"

        # Successful auth
        auth_user, err = authenticate_user("testuser", "SecurePass123!")
        assert err is None
        assert auth_user is not None
        assert auth_user.id == user.id

        # Failed auth
        bad_user, err = authenticate_user("testuser", "WrongPassword123!")
        assert bad_user is None
        assert "Incorrect ID or password" in err

def test_brute_force_lockout(app_with_mock_db):
    with app_with_mock_db.app_context():
        user, _ = register_user("locktest", "lock@example.com", "SecurePass123!")
        
        # 5 failed attempts
        for _ in range(5):
            authenticate_user("locktest", "WrongPass123!")

        # 6th attempt should return locked message
        locked_user, err = authenticate_user("locktest", "SecurePass123!")
        assert locked_user is None
        assert "locked" in err.lower()
