from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, current_user, login_required
from bson import ObjectId
from .services import (
    register_user, authenticate_user, check_username_available, check_email_available,
    create_email_verification_token, verify_email_token,
    create_password_reset_token, reset_password_with_token,
    send_password_reset_email, send_test_email
)
from .oauth import oauth, handle_social_identity
from ..db import user_settings_col, users_col

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/signup", methods=["GET"])
def signup_page():
    if current_user.is_authenticated:
        return redirect(url_for("public.dashboard_page"))
    return render_template("pages/signup.html")

@auth_bp.route("/login", methods=["GET"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("public.dashboard_page"))
    next_url = request.args.get("next", "")
    return render_template("pages/login.html", next_url=next_url)

@auth_bp.route("/logout", methods=["GET", "POST"])
def logout_route():
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login_page"))

@auth_bp.route("/forgot-password", methods=["GET"])
def forgot_password_page():
    return render_template("pages/forgot_password.html")

@auth_bp.route("/reset/<token>", methods=["GET"])
def reset_password_page(token):
    return render_template("pages/reset_password.html", token=token)

@auth_bp.route("/auth/verify/<token>", methods=["GET"])
def verify_email_route(token):
    success = verify_email_token(token)
    if success:
        flash("Your email address has been successfully verified!", "success")
    else:
        flash("The verification link is invalid or has expired.", "danger")
    return redirect(url_for("auth.login_page"))

# REST Endpoints
@auth_bp.route("/api/auth/check", methods=["GET"])
def check_availability():
    username = request.args.get("username")
    email = request.args.get("email")
    if username is not None:
        avail = check_username_available(username)
        return jsonify({"ok": True, "data": {"available": avail}})
    if email is not None:
        avail = check_email_available(email)
        return jsonify({"ok": True, "data": {"available": avail}})
    return jsonify({"ok": False, "error": {"code": "missing_param", "message": "Specify username or email."}}), 400

@auth_bp.route("/api/auth/signup", methods=["POST"])
def signup_api():
    data = request.get_json() or {}
    username = data.get("username", "")
    email = data.get("email", "")
    password = data.get("password", "")
    accept = data.get("accept", False)

    if not accept:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": "You must accept the Terms and Privacy Policy."}}), 400

    ip = request.remote_addr or ""
    ua = request.user_agent.string if request.user_agent else ""
    user, err = register_user(username, email, password, ip=ip, user_agent=ua)
    if err:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": err}}), 400

    login_user(user, remember=True)
    # Generate verification token
    raw_token = create_email_verification_token(ObjectId(user.id))
    
    return jsonify({
        "ok": True,
        "data": {
            "user": user.to_dict(),
            "verification_token": raw_token,
            "message": "Account created successfully."
        }
    }), 201

@auth_bp.route("/api/auth/login", methods=["POST"])
def login_api():
    data = request.get_json() or {}
    identifier = data.get("identifier", "")
    password = data.get("password", "")
    remember = bool(data.get("remember", False))

    ip = request.remote_addr or ""
    ua = request.user_agent.string if request.user_agent else ""
    user, err = authenticate_user(identifier, password, ip=ip, user_agent=ua)
    if err:
        return jsonify({"ok": False, "error": {"code": "unauthorized", "message": err}}), 401

    login_user(user, remember=remember)
    return jsonify({
        "ok": True,
        "data": {
            "user": user.to_dict(),
            "message": "Logged in successfully."
        }
    })

@auth_bp.route("/api/auth/logout", methods=["POST"])
@login_required
def logout_api():
    logout_user()
    return jsonify({"ok": True, "data": {"message": "Logged out."}})

@auth_bp.route("/api/auth/logout-all", methods=["POST"])
@login_required
def logout_all_api():
    logout_user()
    return jsonify({"ok": True, "data": {"message": "Logged out of all sessions."}})

@auth_bp.route("/api/auth/forgot", methods=["POST"])
def forgot_api():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    token = create_password_reset_token(email)
    
    # Send actual email via configured SMTP if token generated
    email_sent = False
    if token:
        email_sent = send_password_reset_email(email, token)

    return jsonify({
        "ok": True,
        "data": {
            "message": "If an account with that email exists, password reset instructions have been sent to your inbox.",
            "email_sent": email_sent,
            "reset_token": token if request.host.startswith("localhost") else None
        }
    })

@auth_bp.route("/api/auth/test-smtp", methods=["POST"])
def test_smtp_api():
    data = request.get_json() or {}
    recipient = data.get("email") or (current_user.email if current_user.is_authenticated else None) or current_app.config.get("MAIL_USERNAME")
    if not recipient:
        return jsonify({"ok": False, "error": {"code": "missing_recipient", "message": "Please provide an email address."}}), 400

    ok, err = send_test_email(recipient)
    if not ok:
        return jsonify({"ok": False, "error": {"code": "smtp_error", "message": f"SMTP test failed: {err}"}}), 500

    return jsonify({
        "ok": True,
        "data": {
            "message": f"Test email sent successfully to {recipient}!",
            "recipient": recipient
        }
    })

@auth_bp.route("/api/auth/reset", methods=["POST"])
def reset_api():
    data = request.get_json() or {}
    token = data.get("token", "")
    password = data.get("password", "")
    confirm = data.get("confirm", "")
    
    if password != confirm:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": "Passwords do not match."}}), 400
        
    ok, err = reset_password_with_token(token, password)
    if not ok:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": err}}), 400
        
    return jsonify({"ok": True, "data": {"message": "Password reset successful. Please log in with your new password."}})

@auth_bp.route("/api/auth/me", methods=["GET"])
def me_api():
    if not current_user.is_authenticated:
        return jsonify({"ok": True, "data": {"authenticated": False, "user": None}})
        
    settings_doc = user_settings_col().find_one({"user_id": ObjectId(current_user.id)}) or {}
    return jsonify({
        "ok": True,
        "data": {
            "authenticated": True,
            "user": current_user.to_dict(),
            "settings": {
                "appearance": settings_doc.get("appearance", {}),
                "sync": settings_doc.get("sync", {}),
                "notifications": settings_doc.get("notifications", {})
            }
        }
    })

@auth_bp.route("/auth/<provider>/start", methods=["GET"])
@auth_bp.route("/auth/oauth/<provider>", methods=["GET"])
def oauth_start(provider):
    if provider not in ("google", "microsoft", "yahoo", "apple"):
        flash("Unsupported authentication provider.", "danger")
        return redirect(url_for("auth.login_page"))

    client = getattr(oauth, provider, None)
    has_keys = bool(current_app.config.get(f"{provider.upper()}_CLIENT_ID") if provider != "microsoft" else current_app.config.get("MS_CLIENT_ID"))

    if not client or not has_keys:
        # Fallback to mock identity for testing/demo
        mock_email = f"demo_{provider}@mailshield.example"
        user, err = handle_social_identity(
            provider=provider,
            subject=f"mock_{provider}_sub_12345",
            email=mock_email,
            name=f"Demo {provider.capitalize()} User",
            email_verified=True,
            ip=request.remote_addr or "",
            user_agent=request.user_agent.string if request.user_agent else ""
        )
        if user:
            login_user(user)
            flash(f"Signed in as {user.display_name} (Mock Mode).", "info")
            return redirect(url_for("mail.dashboard_page"))
        else:
            flash(err or "Failed to authenticate.", "danger")
            return redirect(url_for("auth.login_page"))

    base_url = current_app.config.get("BASE_URL", "http://localhost:5000").rstrip("/")
    redirect_uri = current_app.config.get(f"{provider.upper()}_AUTH_REDIRECT_URI") or f"{base_url}/auth/oauth/{provider}/callback"
    return client.authorize_redirect(redirect_uri)

@auth_bp.route("/auth/<provider>/callback", methods=["GET", "POST"])
@auth_bp.route("/auth/oauth/<provider>/callback", methods=["GET", "POST"])
def oauth_callback(provider):
    if provider not in ("google", "microsoft", "yahoo", "apple"):
        flash("Unsupported authentication provider.", "danger")
        return redirect(url_for("auth.login_page"))

    client = getattr(oauth, provider, None)
    if not client:
        flash("Authentication client not initialized.", "danger")
        return redirect(url_for("auth.login_page"))

    try:
        token = client.authorize_access_token()
        userinfo = token.get("userinfo")
        if not userinfo:
            try:
                userinfo = client.userinfo()
            except Exception:
                userinfo = {}

        subject = userinfo.get("sub") or userinfo.get("id") or token.get("sub")
        email = userinfo.get("email") or ""
        name = userinfo.get("name") or userinfo.get("login") or (email.split("@")[0] if email else "")
        avatar_url = userinfo.get("picture") or userinfo.get("avatar_url") or ""
        email_verified = userinfo.get("email_verified", True)

        if not subject:
            flash("Could not obtain user profile from provider.", "danger")
            return redirect(url_for("auth.login_page"))

        user, err = handle_social_identity(
            provider=provider,
            subject=str(subject),
            email=email,
            name=name,
            avatar_url=avatar_url,
            email_verified=email_verified,
            ip=request.remote_addr or "",
            user_agent=request.user_agent.string if request.user_agent else ""
        )
        if err or not user:
            flash(err or "Failed to log in with social identity.", "danger")
            return redirect(url_for("auth.login_page"))

        login_user(user)
        flash(f"Welcome back, {user.display_name}!", "success")
        return redirect(url_for("mail.dashboard_page"))
    except Exception as e:
        current_app.logger.error(f"OAuth Callback Error for {provider}: {e}")
        flash(f"Authentication failed: {str(e)}", "danger")
        return redirect(url_for("auth.login_page"))

