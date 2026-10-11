import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base application configuration."""
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    SECRET_KEY = os.getenv("SECRET_KEY", "mailshield-default-secret-key-change-in-production")
    FERNET_KEY = os.getenv("FERNET_KEY", "vMy4iU1j_xJqMsmL6U2t1PzQ9Rz-3H6w_t7vU8xY0zA=")
    
    # MongoDB
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB = os.getenv("MONGO_DB", "mailshield")
    
    # Domain / URLs
    BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
    WEBHOOKS_ENABLED = os.getenv("WEBHOOKS_ENABLED", "false").lower() in ("true", "1", "yes")
    
    # Session
    SESSION_DAYS = int(os.getenv("SESSION_DAYS", "7"))
    PERMANENT_SESSION_LIFETIME = timedelta(days=SESSION_DAYS)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = FLASK_ENV == "production"
    
    # Sync limits
    MAX_SYNC_PAGE = int(os.getenv("MAX_SYNC_PAGE", "50"))
    
    # Google
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_AUTH_REDIRECT_URI = os.getenv("GOOGLE_AUTH_REDIRECT_URI", "")
    GOOGLE_MAIL_REDIRECT_URI = os.getenv("GOOGLE_MAIL_REDIRECT_URI", "")
    GOOGLE_PUBSUB_TOPIC = os.getenv("GOOGLE_PUBSUB_TOPIC", "")
    GOOGLE_PUBSUB_AUDIENCE = os.getenv("GOOGLE_PUBSUB_AUDIENCE", "")
    GOOGLE_PUBSUB_SA_EMAIL = os.getenv("GOOGLE_PUBSUB_SA_EMAIL", "")
    
    # Microsoft
    MS_CLIENT_ID = os.getenv("MS_CLIENT_ID", "")
    MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET", "")
    MS_TENANT = os.getenv("MS_TENANT", "common")
    MS_WEBHOOK_SECRET = os.getenv("MS_WEBHOOK_SECRET", "")
    
    # Yahoo
    YAHOO_CLIENT_ID = os.getenv("YAHOO_CLIENT_ID", "")
    YAHOO_CLIENT_SECRET = os.getenv("YAHOO_CLIENT_SECRET", "")
    
    # Apple
    APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID", "")
    APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID", "")
    APPLE_KEY_ID = os.getenv("APPLE_KEY_ID", "")
    APPLE_PRIVATE_KEY_PATH = os.getenv("APPLE_PRIVATE_KEY_PATH", "./secrets/AuthKey_XXXX.p8")
    
    # Flask-Mail (SMTP)
    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "1025"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "false").lower() in ("true", "1", "yes")
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() in ("true", "1", "yes")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "").strip()
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "").strip()
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_FROM", "Mail Shield <no-reply@mailshield.example>").strip()
    
    # Rate Limiting
    RATELIMIT_DEFAULT = "200/hour"
    RATELIMIT_STORAGE_URI = "memory://"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    MONGO_DB = "mailshield_test"
    WTF_CSRF_ENABLED = False
    SERVER_NAME = "localhost.localdomain"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig
}
