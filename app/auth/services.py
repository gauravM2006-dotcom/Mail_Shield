import re
import datetime
from bson import ObjectId
from typing import Tuple, Optional, Dict, Any
from flask import current_app, url_for
from flask_mail import Message
from ..db import users_col, auth_tokens_col, user_settings_col, rule_configs_col, audit_logs_col
from ..security import hash_password, verify_password, generate_token, hash_token
from ..rules.defaults import get_default_rule_config
from ..extensions import mail_ext
from .models import User

def is_valid_password(password: str) -> bool:
    """Validate password: min 8 chars, uppercase, lowercase, digit, symbol."""
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_]', password):
        return False
    return True

def is_valid_username(username: str) -> bool:
    """Username 3-30 chars: letters, digits, _, ., -."""
    return bool(re.match(r'^[a-zA-Z0-9_.-]{3,30}$', username))

def check_username_available(username: str) -> bool:
    if not is_valid_username(username):
        return False
    return users_col().find_one({"username": username.lower().strip()}) is None

def check_email_available(email: str) -> bool:
    clean_email = email.lower().strip()
    return users_col().find_one({"email": clean_email}) is None

def initialize_user_defaults(user_id: ObjectId):
    """Create initial user_settings and copy system-default rule_configs for a new user."""
    # 1. user_settings
    user_settings_col().update_one(
        {"user_id": user_id},
        {"$setOnInsert": {
            "user_id": user_id,
            "appearance": {
                "theme": "follow_system",
                "accent": "blue",
                "density": "comfortable",
                "font_size": "medium",
                "sidebar_collapsed": False,
                "reduce_motion": False
            },
            "sync": {
                "depth_days": 30,
                "auto_scan_all": False,
                "auto_scan_providers": {"gmail": False, "outlook": False, "yahoo": False, "icloud": False},
                "retention_days": 90,
                "default_scan_mode": "unscanned",
                "enable_dns_checks": False
            },
            "notifications": {
                "toast_new_mail": True,
                "toast_spam": True,
                "sound": False,
                "desktop": False
            },
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }},
        upsert=True
    )
    
    # 2. rule_configs (clone default)
    default_cfg = get_default_rule_config()
    default_cfg["user_id"] = user_id
    default_cfg["created_at"] = datetime.datetime.now(datetime.timezone.utc)
    default_cfg["updated_at"] = datetime.datetime.now(datetime.timezone.utc)
    rule_configs_col().update_one(
        {"user_id": user_id},
        {"$setOnInsert": default_cfg},
        upsert=True
    )

def log_audit_event(user_id: Optional[ObjectId], action: str, ip: str, user_agent: str, meta: Dict[str, Any] = None):
    audit_logs_col().insert_one({
        "user_id": user_id,
        "action": action,
        "ip": ip,
        "user_agent": user_agent,
        "meta": meta or {},
        "created_at": datetime.datetime.now(datetime.timezone.utc)
    })

def register_user(username: str, email: str, password: str, ip: str = "", user_agent: str = "") -> Tuple[Optional[User], Optional[str]]:
    username_clean = username.strip().lower()
    email_clean = email.strip().lower()
    
    if not is_valid_username(username_clean):
        return None, "Username must be 3-30 characters (letters, numbers, _, ., -)."
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email_clean):
        return None, "Invalid email address format."
    if not is_valid_password(password):
        return None, "Password must be at least 8 characters with upper, lower, digit and symbol."
        
    if not check_username_available(username_clean):
        return None, "Username is already taken."
    if not check_email_available(email_clean):
        return None, "An account with this email already exists."
        
    pwd_hash = hash_password(password)
    user_doc = {
        "username": username_clean,
        "display_username": username.strip(),
        "email": email_clean,
        "email_verified": False,
        "password_hash": pwd_hash,
        "display_name": username.strip(),
        "avatar_url": "",
        "identities": [],
        "status": "active",
        "failed_logins": 0,
        "locked_until": None,
        "created_at": datetime.datetime.now(datetime.timezone.utc),
        "last_login_at": datetime.datetime.now(datetime.timezone.utc)
    }
    
    res = users_col().insert_one(user_doc)
    user_id = res.inserted_id
    user_doc["_id"] = user_id
    
    initialize_user_defaults(user_id)
    log_audit_event(user_id, "signup_password", ip, user_agent, {"email": email_clean})
    
    return User.from_doc(user_doc), None

def authenticate_user(identifier: str, password: str, ip: str = "", user_agent: str = "") -> Tuple[Optional[User], Optional[str]]:
    ident_clean = identifier.strip().lower()
    user_doc = users_col().find_one({
        "$or": [{"username": ident_clean}, {"email": ident_clean}]
    })
    
    generic_error = "Incorrect ID or password."
    if not user_doc:
        return None, generic_error
        
    now = datetime.datetime.now(datetime.timezone.utc)
    locked_until = user_doc.get("locked_until")
    # Normalize naive datetimes (from mongomock or older records) to UTC-aware
    if locked_until and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=datetime.timezone.utc)
    if locked_until and locked_until > now:
        mins_left = int((locked_until - now).total_seconds() / 60) + 1
        return None, f"Too many failed login attempts. Account is locked for {mins_left} minutes."
        
    pwd_hash = user_doc.get("password_hash")
    if not pwd_hash:
        return None, "This account uses social sign-in. Please log in with your connected provider."
        
    if not verify_password(pwd_hash, password):
        failed = user_doc.get("failed_logins", 0) + 1
        update_fields = {"failed_logins": failed}
        if failed >= 5:
            update_fields["locked_until"] = now + datetime.timedelta(minutes=15)
            log_audit_event(user_doc["_id"], "account_locked_brute_force", ip, user_agent)
        users_col().update_one({"_id": user_doc["_id"]}, {"$set": update_fields})
        return None, generic_error
        
    # Reset failure counter on success
    users_col().update_one(
        {"_id": user_doc["_id"]},
        {"$set": {"failed_logins": 0, "locked_until": None, "last_login_at": now}}
    )
    
    log_audit_event(user_doc["_id"], "login_success", ip, user_agent)
    return User.from_doc(user_doc), None

def create_email_verification_token(user_id: ObjectId) -> str:
    raw_token = generate_token(32)
    token_h = hash_token(raw_token)
    expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)
    
    auth_tokens_col().insert_one({
        "user_id": user_id,
        "type": "verify_email",
        "token_hash": token_h,
        "expires_at": expires,
        "used_at": None
    })
    return raw_token

def verify_email_token(raw_token: str) -> bool:
    token_h = hash_token(raw_token)
    now = datetime.datetime.now(datetime.timezone.utc)
    doc = auth_tokens_col().find_one({
        "token_hash": token_h,
        "type": "verify_email",
        "expires_at": {"$gt": now},
        "used_at": None
    })
    if not doc:
        return False
        
    auth_tokens_col().update_one({"_id": doc["_id"]}, {"$set": {"used_at": now}})
    users_col().update_one({"_id": doc["user_id"]}, {"$set": {"email_verified": True}})
    return True

def create_password_reset_token(email: str) -> Optional[str]:
    email_clean = email.strip().lower()
    user_doc = users_col().find_one({"email": email_clean})
    if not user_doc:
        return None
        
    raw_token = generate_token(32)
    token_h = hash_token(raw_token)
    expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)
    
    auth_tokens_col().insert_one({
        "user_id": user_doc["_id"],
        "type": "reset_password",
        "token_hash": token_h,
        "expires_at": expires,
        "used_at": None
    })
    return raw_token

def reset_password_with_token(raw_token: str, new_password: str) -> Tuple[bool, Optional[str]]:
    if not is_valid_password(new_password):
        return False, "Password must be at least 8 characters with upper, lower, digit and symbol."
        
    token_h = hash_token(raw_token)
    now = datetime.datetime.now(datetime.timezone.utc)
    doc = auth_tokens_col().find_one({
        "token_hash": token_h,
        "type": "reset_password",
        "expires_at": {"$gt": now},
        "used_at": None
    })
    if not doc:
        return False, "Password reset link is invalid or has expired."
        
    new_hash = hash_password(new_password)
    users_col().update_one(
        {"_id": doc["user_id"]},
        {"$set": {"password_hash": new_hash, "failed_logins": 0, "locked_until": None}}
    )
    auth_tokens_col().update_one({"_id": doc["_id"]}, {"$set": {"used_at": now}})
    return True, None

def send_password_reset_email(email: str, token: str) -> bool:
    """Send an HTML/text password reset email using configured SMTP provider."""
    try:
        base_url = current_app.config.get("BASE_URL", "http://localhost:5000")
        reset_link = f"{base_url}/reset-password?token={token}"
        msg = Message(
            subject="Mail Shield — Password Reset Request",
            recipients=[email.strip()]
        )
        msg.body = f"""Hello,

We received a request to reset your Mail Shield account password.

Click the link below to set a new password (valid for 30 minutes):
{reset_link}

If you did not request this, you can safely ignore this email. Your password will remain unchanged.

Best regards,
The Mail Shield Security Team
"""
        msg.html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 580px; margin: 0 auto; padding: 24px; border: 1px solid #E2E8F0; border-radius: 12px; background: #ffffff;">
          <h2 style="color: #0F172A; margin-top: 0;">Password Reset Request</h2>
          <p style="color: #475569; font-size: 15px; line-height: 1.6;">
            We received a request to reset your <strong>Mail Shield</strong> account password.
          </p>
          <div style="margin: 28px 0;">
            <a href="{reset_link}" style="background: #2563EB; color: #ffffff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px; display: inline-block;">
              Reset Password
            </a>
          </div>
          <p style="color: #64748B; font-size: 13px; line-height: 1.5;">
            Or copy and paste this link into your browser:<br>
            <a href="{reset_link}" style="color: #2563EB; word-break: break-all;">{reset_link}</a>
          </p>
          <hr style="border: none; border-top: 1px solid #E2E8F0; margin: 24px 0;">
          <p style="color: #94A3B8; font-size: 12px; margin-bottom: 0;">
            This link will expire in 30 minutes. If you did not make this request, you can safely ignore this email.
          </p>
        </div>
        """
        mail_ext.send(msg)
        return True
    except Exception as e:
        current_app.logger.warning(f"Failed to send password reset email to {email}: {e}")
        return False

def send_test_email(to_email: str) -> Tuple[bool, Optional[str]]:
    """Send a diagnostic test email to confirm SMTP connectivity."""
    try:
        msg = Message(
            subject="Mail Shield — SMTP Test Email",
            recipients=[to_email.strip()]
        )
        msg.body = "This is a test email confirming that Mail Shield's outgoing SMTP integration is functioning successfully."
        msg.html = """
        <div style="font-family: sans-serif; max-width: 560px; margin: 0 auto; padding: 20px; border: 1px solid #E2E8F0; border-radius: 10px;">
          <h2 style="color: #10B981; margin-top: 0;">SMTP Test Successful</h2>
          <p style="color: #334155; font-size: 15px;">Your Mail Shield SMTP configuration is working properly.</p>
          <p style="color: #64748B; font-size: 12px;">Automated security notification delivery is active.</p>
        </div>
        """
        mail_ext.send(msg)
        return True, None
    except Exception as e:
        return False, str(e)
