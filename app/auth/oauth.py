import os
import time
import secrets
import re
import datetime
import jwt
from typing import Dict, Any, Optional, Tuple
from bson import ObjectId
from authlib.integrations.flask_client import OAuth
from flask import current_app, url_for, session
from ..db import users_col, audit_logs_col
from .models import User
from .services import initialize_user_defaults, log_audit_event

oauth = OAuth()

def init_oauth(app):
    """Register OAuth clients with Authlib."""
    oauth.init_app(app)
    
    # Google
    if app.config.get("GOOGLE_CLIENT_ID"):
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"}
        )
        oauth.register(
            name="google_mail",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={
                "scope": "openid email profile https://www.googleapis.com/auth/gmail.readonly"
            }
        )
        
    # Microsoft
    if app.config.get("MS_CLIENT_ID"):
        tenant = app.config.get("MS_TENANT", "common")
        oauth.register(
            name="microsoft",
            client_id=app.config["MS_CLIENT_ID"],
            client_secret=app.config["MS_CLIENT_SECRET"],
            server_metadata_url=f"https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile User.Read"}
        )

    # Yahoo
    if app.config.get("YAHOO_CLIENT_ID"):
        oauth.register(
            name="yahoo",
            client_id=app.config["YAHOO_CLIENT_ID"],
            client_secret=app.config["YAHOO_CLIENT_SECRET"],
            server_metadata_url="https://api.login.yahoo.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"}
        )

def generate_apple_client_secret(app) -> Optional[str]:
    """Generate short-lived ES256 signed client_secret JWT for Apple."""
    key_path = app.config.get("APPLE_PRIVATE_KEY_PATH")
    team_id = app.config.get("APPLE_TEAM_ID")
    client_id = app.config.get("APPLE_CLIENT_ID")
    key_id = app.config.get("APPLE_KEY_ID")
    
    if not (key_path and os.path.exists(key_path) and team_id and client_id and key_id):
        return None
        
    with open(key_path, "r") as f:
        private_key = f.read()
        
    now = int(time.time())
    headers = {"kid": key_id, "alg": "ES256"}
    payload = {
        "iss": team_id,
        "iat": now,
        "exp": now + 86400 * 180, # 180 days
        "aud": "https://appleid.apple.com",
        "sub": client_id
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)

def handle_social_identity(
    provider: str,
    subject: str,
    email: str,
    name: str = "",
    avatar_url: str = "",
    email_verified: bool = True,
    ip: str = "",
    user_agent: str = ""
) -> Tuple[Optional[User], Optional[str]]:
    """
    Apply Account matching and linking rules from Blueprint Section 9.4:
    1. Match on identities.provider + identities.subject -> log in.
    2. If not found and provider says email is verified, and user with same email exists and is verified -> link identity.
    3. If user exists with same email but is NOT verified -> refuse linking.
    4. Otherwise create new user account.
    """
    clean_email = email.strip().lower() if email else ""
    now = time.time()
    
    # Rule 1: Match on existing provider identity
    existing_by_sub = users_col().find_one({
        "identities": {"$elemMatch": {"provider": provider, "subject": subject}}
    })
    if existing_by_sub:
        users_col().update_one(
            {"_id": existing_by_sub["_id"]},
            {"$set": {"last_login_at": datetime.datetime.now(datetime.timezone.utc)}}
        )
        log_audit_event(existing_by_sub["_id"], f"login_oauth_{provider}", ip, user_agent)
        return User.from_doc(existing_by_sub), None

    # Rule 2 & 3: Match on email
    if clean_email:
        existing_by_email = users_col().find_one({"email": clean_email})
        if existing_by_email:
            if email_verified and existing_by_email.get("email_verified", False):
                # Link new identity
                identity_entry = {
                    "provider": provider,
                    "subject": subject,
                    "email": clean_email,
                    "linked_at": datetime.datetime.now(datetime.timezone.utc)
                }
                users_col().update_one(
                    {"_id": existing_by_email["_id"]},
                    {
                        "$push": {"identities": identity_entry},
                        "$set": {"last_login_at": datetime.datetime.now(datetime.timezone.utc)}
                    }
                )
                log_audit_event(existing_by_email["_id"], f"link_oauth_{provider}", ip, user_agent)
                existing_by_email["identities"].append(identity_entry)
                return User.from_doc(existing_by_email), None
            else:
                return None, "An account with this email already exists. Please log in with your password, then link your provider under Account Settings."

    # Rule 4: Create new user
    base_user = clean_email.split("@")[0] if clean_email else f"{provider}_user"
    base_user = re.sub(r'[^a-zA-Z0-9_.-]', '', base_user)[:20] or "user"
    
    # Generate unique username
    candidate = base_user
    counter = 1
    while users_col().find_one({"username": candidate.lower()}):
        candidate = f"{base_user}_{secrets.randbelow(9000)+1000}"
        counter += 1
        if counter > 10:
            break

    user_doc = {
        "username": candidate.lower(),
        "display_username": candidate,
        "email": clean_email or f"{subject}@{provider}.mailshield.local",
        "email_verified": email_verified,
        "password_hash": None,
        "display_name": name or candidate,
        "avatar_url": avatar_url or "",
        "identities": [{
            "provider": provider,
            "subject": subject,
            "email": clean_email,
            "linked_at": datetime.datetime.now(datetime.timezone.utc)
        }],
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
    log_audit_event(user_id, f"signup_oauth_{provider}", ip, user_agent)
    
    return User.from_doc(user_doc), None
