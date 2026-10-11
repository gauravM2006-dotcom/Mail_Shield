import json
from flask import Blueprint, render_template, request, jsonify, Response
from flask_login import login_required, current_user, logout_user
from bson import ObjectId
from ..db import users_col, mail_accounts_col, emails_col, scans_col, scan_batches_col, rule_configs_col, user_settings_col, audit_logs_col
from ..security import hash_password, verify_password
from ..auth.services import is_valid_password, is_valid_username, log_audit_event

account_bp = Blueprint("account", __name__)

@account_bp.route("/account", methods=["GET"])
@login_required
def account_page():
    return render_template("pages/account.html")

@account_bp.route("", methods=["GET"])
@login_required
def get_account_details():
    user_id = ObjectId(current_user.id)
    u_doc = users_col().find_one({"_id": user_id})
    if not u_doc:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "User not found."}}), 404

    mailboxes = list(mail_accounts_col().find({"user_id": user_id}))
    mb_list = []
    for mb in mailboxes:
        mb_list.append({
            "provider": mb.get("provider"),
            "address": mb.get("address"),
            "status": mb.get("status"),
            "connected_at": mb.get("created_at").isoformat() + "Z" if mb.get("created_at") else None,
            "last_sync_at": mb.get("last_sync_at").isoformat() + "Z" if mb.get("last_sync_at") else None,
            "cached": emails_col().count_documents({"account_id": mb["_id"]})
        })

    return jsonify({
        "ok": True,
        "data": {
            "username": u_doc.get("username"),
            "display_name": u_doc.get("display_name"),
            "email": u_doc.get("email"),
            "email_verified": u_doc.get("email_verified", False),
            "has_password": u_doc.get("password_hash") is not None,
            "avatar_url": u_doc.get("avatar_url", ""),
            "created_at": u_doc.get("created_at").isoformat() + "Z" if u_doc.get("created_at") else None,
            "identities": u_doc.get("identities", []),
            "mailboxes": mb_list
        }
    })

@account_bp.route("/profile", methods=["PATCH"])
@login_required
def update_profile():
    user_id = ObjectId(current_user.id)
    data = request.get_json() or {}
    display_name = data.get("display_name", "").strip()

    updates = {}
    if display_name:
        updates["display_name"] = display_name

    if updates:
        users_col().update_one({"_id": user_id}, {"$set": updates})

    return jsonify({"ok": True, "data": {"message": "Profile updated."}})

@account_bp.route("/password", methods=["POST"])
@login_required
def change_password():
    user_id = ObjectId(current_user.id)
    u_doc = users_col().find_one({"_id": user_id})
    data = request.get_json() or {}

    current_pwd = data.get("current", "")
    new_pwd = data.get("new", "")
    confirm_pwd = data.get("confirm", "")

    if new_pwd != confirm_pwd:
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": "Passwords do not match."}}), 400

    if not is_valid_password(new_pwd):
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": "Password must be at least 8 characters with upper, lower, digit and symbol."}}), 400

    # If user currently has a password, verify it
    if u_doc.get("password_hash"):
        if not verify_password(u_doc["password_hash"], current_pwd):
            return jsonify({"ok": False, "error": {"code": "invalid_password", "message": "Current password is incorrect."}}), 400

    new_hash = hash_password(new_pwd)
    users_col().update_one({"_id": user_id}, {"$set": {"password_hash": new_hash}})
    log_audit_event(user_id, "password_changed", request.remote_addr or "", request.user_agent.string if request.user_agent else "")

    return jsonify({"ok": True, "data": {"message": "Password updated successfully."}})

@account_bp.route("/activity", methods=["GET"])
@login_required
def get_activity():
    user_id = ObjectId(current_user.id)
    logs = list(audit_logs_col().find({"user_id": user_id}).sort([("created_at", -1)]).limit(10))
    result = []
    for l in logs:
        result.append({
            "action": l.get("action"),
            "ip": l.get("ip"),
            "user_agent": l.get("user_agent"),
            "created_at": l.get("created_at").isoformat() + "Z" if l.get("created_at") else None
        })
    return jsonify({"ok": True, "data": result})

@account_bp.route("/export", methods=["GET"])
@login_required
def export_all_data():
    user_id = ObjectId(current_user.id)
    u_doc = users_col().find_one({"_id": user_id})
    if not u_doc:
        return jsonify({"ok": False}), 404
    u_doc["_id"] = str(u_doc["_id"])
    u_doc.pop("password_hash", None)

    cfg = rule_configs_col().find_one({"user_id": user_id}) or {}
    cfg.pop("_id", None)
    cfg.pop("user_id", None)

    settings = user_settings_col().find_one({"user_id": user_id}) or {}
    settings.pop("_id", None)
    settings.pop("user_id", None)

    bundle = {
        "user_profile": u_doc,
        "rule_configuration": cfg,
        "preferences": settings,
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
    }

    return Response(
        json.dumps(bundle, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=mailshield_user_archive.json"}
    )

@account_bp.route("", methods=["DELETE"])
@login_required
def delete_account():
    data = request.get_json() or {}
    confirm = data.get("confirm", "")
    if confirm != "DELETE":
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": "Please type DELETE to confirm."}}), 400

    user_id = ObjectId(current_user.id)
    
    # Delete all documents belonging to user
    emails_col().delete_many({"user_id": user_id})
    scans_col().delete_many({"user_id": user_id})
    scan_batches_col().delete_many({"user_id": user_id})
    mail_accounts_col().delete_many({"user_id": user_id})
    rule_configs_col().delete_many({"user_id": user_id})
    user_settings_col().delete_many({"user_id": user_id})
    audit_logs_col().delete_many({"user_id": user_id})
    users_col().delete_one({"_id": user_id})

    logout_user()
    return jsonify({"ok": True, "data": {"message": "Your account and all associated data have been permanently deleted."}})
