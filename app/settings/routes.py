from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from bson import ObjectId
from ..db import user_settings_col

settings_bp = Blueprint("settings", __name__)

@settings_bp.route("/settings", methods=["GET"])
@login_required
def settings_page():
    return render_template("pages/settings.html")

@settings_bp.route("", methods=["GET"])
@login_required
def get_settings():
    user_id = ObjectId(current_user.id)
    doc = user_settings_col().find_one({"user_id": user_id}) or {}
    return jsonify({
        "ok": True,
        "data": {
            "appearance": doc.get("appearance", {}),
            "sync": doc.get("sync", {}),
            "notifications": doc.get("notifications", {})
        }
    })

@settings_bp.route("", methods=["PATCH"])
@login_required
def update_settings():
    user_id = ObjectId(current_user.id)
    data = request.get_json() or {}

    update_fields = {}
    if "appearance" in data:
        for k, v in data["appearance"].items():
            update_fields[f"appearance.{k}"] = v
    if "sync" in data:
        for k, v in data["sync"].items():
            update_fields[f"sync.{k}"] = v
    if "notifications" in data:
        for k, v in data["notifications"].items():
            update_fields[f"notifications.{k}"] = v

    if update_fields:
        user_settings_col().update_one(
            {"user_id": user_id},
            {"$set": update_fields},
            upsert=True
        )

    return jsonify({"ok": True, "data": {"message": "Settings saved."}})
