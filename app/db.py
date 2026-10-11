import os
import pymongo
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from flask import current_app, g
from typing import Optional
from .rules.defaults import get_default_rule_config

_client: Optional[MongoClient] = None

def get_mongo_client(uri: Optional[str] = None) -> MongoClient:
    global _client
    if _client is None:
        mongo_uri = uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
        _client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
    return _client

def get_db():
    if "db" not in g:
        client = get_mongo_client(current_app.config.get("MONGO_URI"))
        db_name = current_app.config.get("MONGO_DB", "mailshield")
        g.db = client[db_name]
    return g.db

def close_db(e=None):
    pass

# Collection helpers
def users_col():
    return get_db()["users"]

def auth_tokens_col():
    return get_db()["auth_tokens"]

def mail_accounts_col():
    return get_db()["mail_accounts"]

def emails_col():
    return get_db()["emails"]

def scan_batches_col():
    return get_db()["scan_batches"]

def scans_col():
    return get_db()["scans"]

def rule_configs_col():
    return get_db()["rule_configs"]

def user_settings_col():
    return get_db()["user_settings"]

def audit_logs_col():
    return get_db()["audit_logs"]

def create_indexes(db=None):
    """Create all required unique, compound, and TTL indexes according to Blueprint Section 8.3."""
    target_db = db or get_db()
    
    try:
        # 1. users
        target_db.users.create_index([("username", ASCENDING)], unique=True)
        target_db.users.create_index([("email", ASCENDING)], unique=True)
        target_db.users.create_index([("identities.provider", ASCENDING), ("identities.subject", ASCENDING)], unique=True, sparse=True)
        
        # 2. auth_tokens (TTL on expires_at)
        target_db.auth_tokens.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
        target_db.auth_tokens.create_index([("token_hash", ASCENDING)])
        
        # 3. mail_accounts
        target_db.mail_accounts.create_index([("user_id", ASCENDING), ("provider", ASCENDING)], unique=True)
        target_db.mail_accounts.create_index([("status", ASCENDING)])
        target_db.mail_accounts.create_index([("sync_state.watch_expires_at", ASCENDING)])
        
        # 4. emails
        target_db.emails.create_index([("account_id", ASCENDING), ("provider_msg_id", ASCENDING)], unique=True)
        target_db.emails.create_index([("user_id", ASCENDING), ("provider", ASCENDING), ("received_at", DESCENDING)])
        target_db.emails.create_index([("user_id", ASCENDING), ("current_scan.label", ASCENDING)])
        target_db.emails.create_index([("user_id", ASCENDING), ("is_read", ASCENDING)])
        
        # 5. scan_batches
        target_db.scan_batches.create_index([("user_id", ASCENDING), ("started_at", DESCENDING)])
        target_db.scan_batches.create_index([("status", ASCENDING)])
        
        # 6. scans
        target_db.scans.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        target_db.scans.create_index([("batch_id", ASCENDING)])
        target_db.scans.create_index([("user_id", ASCENDING), ("provider", ASCENDING), ("label", ASCENDING)])
        
        # 7. rule_configs
        target_db.rule_configs.create_index([("user_id", ASCENDING)], unique=True)
        
        # 8. user_settings
        target_db.user_settings.create_index([("user_id", ASCENDING)], unique=True)
        
        # 9. audit_logs (TTL: 180 days = 15552000s)
        target_db.audit_logs.create_index([("created_at", ASCENDING)], expireAfterSeconds=15552000)
        target_db.audit_logs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        
        # Ensure system default rule_configs exists
        existing_default = target_db.rule_configs.find_one({"user_id": None})
        if not existing_default:
            default_cfg = get_default_rule_config()
            target_db.rule_configs.insert_one(default_cfg)
            
    except Exception as e:
        print(f"Warning during index initialization: {e}")
