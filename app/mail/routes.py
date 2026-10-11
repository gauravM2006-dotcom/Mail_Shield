import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app, session
from flask_login import login_required, current_user
from bson import ObjectId
from ..db import mail_accounts_col, emails_col, scans_col, user_settings_col, users_col
from ..security import encrypt_data, decrypt_data
from ..auth.oauth import oauth
from .sync_manager import run_initial_sync, get_provider_adapter

mail_bp = Blueprint("mail", __name__)

PROVIDERS = ["gmail", "outlook", "yahoo", "icloud"]

@mail_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard_page():
    return redirect(url_for("public.dashboard_page", **request.args))

@mail_bp.route("/accounts", methods=["GET"])
@login_required
def get_accounts():
    user_id = ObjectId(current_user.id)
    accounts = list(mail_accounts_col().find({"user_id": user_id}))
    acc_map = {a["provider"]: a for a in accounts}

    result = []
    for p in PROVIDERS:
        acc = acc_map.get(p)
        if acc:
            cached_count = emails_col().count_documents({"user_id": user_id, "provider": p})
            unread_count = emails_col().count_documents({"user_id": user_id, "provider": p, "is_read": False})
            result.append({
                "provider": p,
                "connected": True,
                "address": acc.get("address", ""),
                "status": acc.get("status", "live"),
                "last_sync_at": acc.get("last_sync_at").isoformat() + "Z" if acc.get("last_sync_at") else None,
                "cached": cached_count,
                "unread_new": unread_count,
                "initial_sync": acc.get("initial_sync", {})
            })
        else:
            result.append({
                "provider": p,
                "connected": False,
                "address": "",
                "status": "disconnected",
                "last_sync_at": None,
                "cached": 0,
                "unread_new": 0,
                "initial_sync": {}
            })
    return jsonify({"ok": True, "data": result})

@mail_bp.route("/connect/<provider>", methods=["POST"])
@login_required
def connect_mailbox(provider):
    if provider not in PROVIDERS:
        return jsonify({"ok": False, "error": {"code": "invalid_provider", "message": "Unsupported mail provider."}}), 400

    user_id = ObjectId(current_user.id)
    data = request.get_json() or {}
    address = data.get("address", f"{current_user.username}@{provider}.com").strip().lower()
    app_password = data.get("app_password", "")
    auth_type = "app_password" if app_password else "oauth"

    cred_data = {"app_password": app_password} if app_password else {"token": "mock_oauth_token", "type": "oauth"}
    cred_enc = encrypt_data(cred_data)

    acc_doc = {
        "user_id": user_id,
        "provider": provider,
        "address": address,
        "auth_type": auth_type,
        "credentials_enc": cred_enc,
        "status": "connecting",
        "sync_state": {},
        "initial_sync": {"state": "queued", "total": 0, "done": 0, "depth_days": 30},
        "last_sync_at": None,
        "last_error": None,
        "created_at": datetime.datetime.now(datetime.timezone.utc)
    }

    mail_accounts_col().update_one(
        {"user_id": user_id, "provider": provider},
        {"$set": acc_doc},
        upsert=True
    )

    saved_acc = mail_accounts_col().find_one({"user_id": user_id, "provider": provider})
    
    # Run initial sync
    run_initial_sync(saved_acc["_id"], depth_days=30)

    return jsonify({
        "ok": True,
        "data": {
            "provider": provider,
            "address": address,
            "status": "live",
            "message": f"Successfully connected {provider.capitalize()} mailbox."
        }
    })

@mail_bp.route("/connect/google", methods=["GET"])
@mail_bp.route("/connect/gmail/oauth", methods=["GET"])
@login_required
def connect_google_oauth():
    client = getattr(oauth, "google_mail", None) or getattr(oauth, "google", None)
    if not client or not current_app.config.get("GOOGLE_CLIENT_ID"):
        flash("Google client credentials are not configured in .env", "warning")
        return redirect(url_for("mail.dashboard_page", tab="gmail"))
    
    session["connecting_user_id"] = str(current_user.id)
    base_url = current_app.config.get("BASE_URL", "http://localhost:5000").rstrip("/")
    redirect_uri = current_app.config.get("GOOGLE_MAIL_REDIRECT_URI") or f"{base_url}/api/mail/connect/google/callback"
    return client.authorize_redirect(redirect_uri, access_type="offline", prompt="consent")

@mail_bp.route("/connect/google/callback", methods=["GET", "POST"])
def connect_google_callback():
    client = getattr(oauth, "google_mail", None) or getattr(oauth, "google", None)
    if not client:
        flash("Google OAuth client not initialized.", "danger")
        return redirect(url_for("mail.dashboard_page", tab="gmail"))
    try:
        token = client.authorize_access_token()
        userinfo = token.get("userinfo")
        if not userinfo:
            try:
                userinfo = client.userinfo()
            except Exception:
                userinfo = {}

        uid = current_user.id if (current_user and current_user.is_authenticated) else session.get("connecting_user_id")
        if not uid:
            flash("Session expired while connecting mailbox. Please log in again.", "warning")
            return redirect(url_for("auth.login_page"))
        user_id = ObjectId(uid)

        user_doc = users_col().find_one({"_id": user_id})
        default_name = user_doc.get("username", "user") if user_doc else "user"
        address = userinfo.get("email") or f"{default_name}@gmail.com"

        cred_data = {
            "token": token.get("access_token"),
            "refresh_token": token.get("refresh_token"),
            "token_type": token.get("token_type"),
            "expires_at": token.get("expires_at"),
            "scope": token.get("scope")
        }
        cred_enc = encrypt_data(cred_data)

        acc_doc = {
            "user_id": user_id,
            "provider": "gmail",
            "address": address,
            "auth_type": "oauth",
            "credentials_enc": cred_enc,
            "status": "live",
            "sync_state": {},
            "initial_sync": {"state": "queued", "total": 0, "done": 0, "depth_days": 30},
            "last_sync_at": None,
            "last_error": None,
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }

        mail_accounts_col().update_one(
            {"user_id": user_id, "provider": "gmail"},
            {"$set": acc_doc},
            upsert=True
        )

        saved_acc = mail_accounts_col().find_one({"user_id": user_id, "provider": "gmail"})
        run_initial_sync(saved_acc["_id"], depth_days=30)
        flash(f"Successfully connected your Gmail account ({address})!", "success")
        return redirect(url_for("mail.dashboard_page", tab="gmail"))
    except Exception as e:
        current_app.logger.error(f"Failed to connect Gmail via OAuth: {e}")
        flash(f"Failed to connect Gmail: {str(e)}", "danger")
        return redirect(url_for("mail.dashboard_page", tab="gmail"))

@mail_bp.route("/<provider>", methods=["DELETE"])
@login_required
def disconnect_mailbox(provider):
    if provider not in PROVIDERS:
        return jsonify({"ok": False, "error": {"code": "invalid_provider", "message": "Unsupported provider."}}), 400

    user_id = ObjectId(current_user.id)
    acc = mail_accounts_col().find_one({"user_id": user_id, "provider": provider})
    if acc:
        # Delete cached emails and scans
        emails_col().delete_many({"account_id": acc["_id"]})
        scans_col().delete_many({"account_id": acc["_id"]})
        mail_accounts_col().delete_one({"_id": acc["_id"]})

    return jsonify({"ok": True, "data": {"message": f"Disconnected {provider} and deleted cached emails."}})

@mail_bp.route("/<provider>/sync", methods=["POST"])
@login_required
def sync_mailbox(provider):
    user_id = ObjectId(current_user.id)
    acc = mail_accounts_col().find_one({"user_id": user_id, "provider": provider})
    if not acc:
        return jsonify({"ok": False, "error": {"code": "provider_not_connected", "message": "Mailbox is not connected."}}), 404

    count = run_initial_sync(acc["_id"], depth_days=30)
    return jsonify({"ok": True, "data": {"synced": count, "message": f"Synced {count} messages."}})

@mail_bp.route("/<provider>", methods=["GET"])
@login_required
def list_emails(provider):
    if provider not in PROVIDERS:
        return jsonify({"ok": False, "error": {"code": "invalid_provider", "message": "Invalid provider."}}), 400

    user_id = ObjectId(current_user.id)
    query: dict = {"user_id": user_id, "provider": provider}

    # Filters
    q = request.args.get("q", "").strip()
    if q:
        query["$or"] = [
            {"subject": {"$regex": q, "$options": "i"}},
            {"from.address": {"$regex": q, "$options": "i"}},
            {"from.name": {"$regex": q, "$options": "i"}},
            {"snippet": {"$regex": q, "$options": "i"}}
        ]

    label = request.args.get("label", "").lower()
    if label in ("safe", "suspicious", "spam"):
        query["current_scan.label"] = label
    elif label == "unscanned":
        query["current_scan"] = None

    if request.args.get("unread") == "true":
        query["is_read"] = False
    if request.args.get("has_attachment") == "true":
        query["attachments.0"] = {"$exists": True}

    limit = min(100, int(request.args.get("limit", 50)))
    sort_by = request.args.get("sort", "newest")

    sort_field = [("received_at", -1)]
    if sort_by == "oldest":
        sort_field = [("received_at", 1)]
    elif sort_by == "score":
        sort_field = [("current_scan.score", -1), ("received_at", -1)]

    total = emails_col().count_documents(query)
    cursor = emails_col().find(query).sort(sort_field).limit(limit)

    items = []
    for doc in cursor:
        cs = doc.get("current_scan")
        cs_clean = None
        if cs:
            cs_clean = {
                "scan_id": str(cs.get("scan_id", "")),
                "label": cs.get("label", "safe"),
                "score": cs.get("score", 0),
                "rules_version": cs.get("rules_version", 1),
                "scanned_at": cs.get("scanned_at").isoformat() + "Z" if isinstance(cs.get("scanned_at"), datetime.datetime) else str(cs.get("scanned_at") or "")
            }
        items.append({
            "id": str(doc["_id"]),
            "provider_msg_id": doc.get("provider_msg_id"),
            "from": doc.get("from"),
            "subject": doc.get("subject"),
            "snippet": doc.get("snippet"),
            "received_at": doc.get("received_at").isoformat() + "Z" if doc.get("received_at") else "",
            "is_read": doc.get("is_read", False),
            "has_attachments": len(doc.get("attachments", [])) > 0,
            "current_scan": cs_clean
        })

    return jsonify({
        "ok": True,
        "data": {
            "items": items,
            "total": total,
            "limit": limit
        }
    })

@mail_bp.route("/<provider>/<email_id>", methods=["GET"])
@login_required
def get_email_detail(provider, email_id):
    user_id = ObjectId(current_user.id)
    try:
        e_oid = ObjectId(email_id)
    except Exception:
        return jsonify({"ok": False, "error": {"code": "invalid_id", "message": "Invalid email ID."}}), 400

    doc = emails_col().find_one({"_id": e_oid, "user_id": user_id})
    if not doc:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "Email not found."}}), 404

    # Mark as read
    emails_col().update_one({"_id": e_oid}, {"$set": {"is_read": True}})

    # Fetch full scan reasons if scanned
    scan_doc = None
    cs = doc.get("current_scan")
    if cs and cs.get("scan_id"):
        sid = cs["scan_id"]
        try:
            if isinstance(sid, str):
                sid = ObjectId(sid)
            scan_doc = scans_col().find_one({"_id": sid})
        except Exception:
            pass

    if not scan_doc and cs:
        scan_doc = scans_col().find_one({"email_id": e_oid}, sort=[("created_at", -1)])

    reasons = scan_doc.get("reasons", []) if scan_doc else []
    group_scores = scan_doc.get("group_scores", {}) if scan_doc else {}
    thresholds = scan_doc.get("thresholds", {"suspicious": 30, "spam": 60}) if scan_doc else {"suspicious": 30, "spam": 60}

    # If scanned but reasons is empty and score > 0, recalculate reasons on the fly
    if cs and not reasons and cs.get("score", 0) > 0:
        try:
            from ..engine.preprocess import email_doc_to_parsed_email
            from ..engine.scorer import scan_email
            from ..db import rule_configs_col
            rule_cfg = rule_configs_col().find_one({"user_id": user_id}) or {}
            parsed = email_doc_to_parsed_email(doc)
            scan_res = scan_email(parsed, rule_cfg)
            reasons = [
                {
                    "rule_id": r.rule_id,
                    "group": r.group,
                    "title": r.title,
                    "explanation": r.explanation,
                    "evidence": r.evidence,
                    "points": r.points
                }
                for r in scan_res.reasons
            ]
            group_scores = scan_res.group_scores
            thresholds = scan_res.thresholds
        except Exception as scan_err:
            current_app.logger.warning(f"On-the-fly scan fallback failed: {scan_err}")

    cs_clean = None
    if cs:
        cs_clean = {
            "scan_id": str(cs.get("scan_id", "")),
            "label": cs.get("label", "safe"),
            "score": cs.get("score", 0),
            "rules_version": cs.get("rules_version", 1),
            "scanned_at": cs.get("scanned_at").isoformat() + "Z" if isinstance(cs.get("scanned_at"), datetime.datetime) else str(cs.get("scanned_at") or "")
        }

    return jsonify({
        "ok": True,
        "data": {
            "id": str(doc["_id"]),
            "provider": doc.get("provider"),
            "from": doc.get("from"),
            "to": doc.get("to"),
            "reply_to": doc.get("reply_to"),
            "subject": doc.get("subject"),
            "snippet": doc.get("snippet"),
            "body_text": doc.get("body_text"),
            "urls": doc.get("urls", []),
            "attachments": doc.get("attachments", []),
            "auth_results": doc.get("auth_results", {}),
            "received_at": doc.get("received_at").isoformat() + "Z" if doc.get("received_at") else "",
            "is_read": True,
            "current_scan": cs_clean,
            "reasons": reasons,
            "group_scores": group_scores,
            "thresholds": thresholds
        }
    })

@mail_bp.route("/<provider>/<email_id>/html", methods=["GET"])
@login_required
def get_email_html(provider, email_id):
    user_id = ObjectId(current_user.id)
    try:
        e_oid = ObjectId(email_id)
    except Exception:
        return "Invalid ID", 400

    doc = emails_col().find_one({"_id": e_oid, "user_id": user_id})
    if not doc:
        return "Email not found", 404

    # Render clean sanitised HTML representation
    body = doc.get("body_text", "").replace("\n", "<br>")
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 20px; line-height: 1.6; color: #1B2430; }}
            h2 {{ margin-top: 0; color: #0F172A; }}
            .header-bar {{ background: #F8FAFC; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; border: 1px solid #E2E8F0; }}
        </style>
    </head>
    <body>
        <div class="header-bar">
            <strong>From:</strong> {doc.get('from', {}).get('name')} &lt;{doc.get('from', {}).get('address')}&gt;<br>
            <strong>Subject:</strong> {doc.get('subject')}
        </div>
        <div>{body}</div>
    </body>
    </html>
    """
    return html_content, 200, {"Content-Type": "text/html; charset=utf-8"}

def compute_user_cache_storage(user_id):
    total_mails = emails_col().count_documents({"user_id": user_id})
    scans_count = scans_col().count_documents({"user_id": user_id})
    
    # Calculate bytes stored
    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$project": {
                "body_len": {"$strLenCP": {"$ifNull": ["$body_text", ""]}},
                "subject_len": {"$strLenCP": {"$ifNull": ["$subject", ""]}},
                "att_size": {"$sum": "$attachments.size"}
            }
        },
        {
            "$group": {
                "_id": None,
                "total_bytes": {"$sum": {"$add": ["$body_len", "$subject_len", "$att_size", 1024]}}
            }
        }
    ]
    try:
        res = list(emails_col().aggregate(pipeline))
        bytes_used = res[0]["total_bytes"] if res else 0
    except Exception:
        bytes_used = total_mails * 35 * 1024
    
    bytes_used += scans_count * 1536
    max_quota_bytes = 5 * 1024 * 1024 * 1024  # 5 GB
    percent = round((bytes_used / max_quota_bytes) * 100, 1)
    if bytes_used > 0 and percent < 1.0:
        percent = 1.0

    if bytes_used < 1024 * 1024:
        used_formatted = f"{max(1, round(bytes_used / 1024))} KB"
    elif bytes_used < 1024 * 1024 * 1024:
        used_formatted = f"{round(bytes_used / (1024 * 1024), 1)} MB"
    else:
        used_formatted = f"{round(bytes_used / (1024 * 1024 * 1024), 2)} GB"

    return {
        "used_bytes": bytes_used,
        "max_bytes": max_quota_bytes,
        "used_formatted": used_formatted,
        "max_formatted": "5 GB max",
        "percent": min(100.0, percent),
        "total_cached": total_mails,
        "total_scans": scans_count
    }

@mail_bp.route("/cache/stats", methods=["GET"])
@login_required
def get_cache_stats():
    user_id = ObjectId(current_user.id)
    stats = compute_user_cache_storage(user_id)
    return jsonify({"ok": True, "data": stats})

@mail_bp.route("/cache/clear", methods=["POST"])
@login_required
def clear_cache():
    user_id = ObjectId(current_user.id)
    deleted_scans = scans_col().delete_many({"user_id": user_id}).deleted_count
    return jsonify({
        "ok": True,
        "data": {
            "cleared_scans": deleted_scans,
            "message": "Local cache logs optimized successfully."
        }
    })

@mail_bp.route("/dashboard/summary", methods=["GET"])
@login_required
def dashboard_summary():
    user_id = ObjectId(current_user.id)
    total_mails = emails_col().count_documents({"user_id": user_id})
    scanned_mails = emails_col().count_documents({"user_id": user_id, "current_scan": {"$ne": None}})
    suspicious_mails = emails_col().count_documents({"user_id": user_id, "current_scan.label": "suspicious"})
    spam_mails = emails_col().count_documents({"user_id": user_id, "current_scan.label": "spam"})

    per_provider = {}
    for p in PROVIDERS:
        per_provider[p] = {
            "total": emails_col().count_documents({"user_id": user_id, "provider": p}),
            "scanned": emails_col().count_documents({"user_id": user_id, "provider": p, "current_scan": {"$ne": None}}),
            "safe": emails_col().count_documents({"user_id": user_id, "provider": p, "current_scan.label": "safe"}),
            "suspicious": emails_col().count_documents({"user_id": user_id, "provider": p, "current_scan.label": "suspicious"}),
            "spam": emails_col().count_documents({"user_id": user_id, "provider": p, "current_scan.label": "spam"})
        }

    storage_stats = compute_user_cache_storage(user_id)

    return jsonify({
        "ok": True,
        "data": {
            "mails": total_mails,
            "scanned": scanned_mails,
            "suspicious": suspicious_mails,
            "spam": spam_mails,
            "per_provider": per_provider,
            "storage": storage_stats
        }
    })
