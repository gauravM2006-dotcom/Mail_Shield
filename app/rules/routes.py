import datetime
import json
from flask import Blueprint, render_template, request, jsonify, Response
from flask_login import login_required, current_user
from bson import ObjectId
from ..db import rule_configs_col
from ..rules.defaults import get_default_rule_config
from ..engine import to_parsed_email, scan_email

rules_bp = Blueprint("rules", __name__)

@rules_bp.route("/rules", methods=["GET"])
@login_required
def rules_page():
    return render_template("pages/rules.html")

@rules_bp.route("", methods=["GET"])
@login_required
def get_rules_api():
    user_id = ObjectId(current_user.id)
    cfg = rule_configs_col().find_one({"user_id": user_id})
    if not cfg:
        cfg = get_default_rule_config()
        cfg["user_id"] = user_id
        cfg["created_at"] = datetime.datetime.now(datetime.timezone.utc)
        rule_configs_col().insert_one(cfg)

    cfg["_id"] = str(cfg["_id"])
    cfg["user_id"] = str(cfg["user_id"])
    return jsonify({"ok": True, "data": cfg})

@rules_bp.route("", methods=["PUT"])
@login_required
def save_rules_api():
    user_id = ObjectId(current_user.id)
    data = request.get_json() or {}

    # Validate thresholds
    thresholds = data.get("thresholds", {})
    susp = int(thresholds.get("suspicious", 30))
    spam = int(thresholds.get("spam", 60))

    if not (0 < susp < spam <= 100):
        return jsonify({"ok": False, "error": {"code": "validation_error", "message": "Thresholds must satisfy 0 < suspicious < spam <= 100."}}), 400

    # Read current version
    current_doc = rule_configs_col().find_one({"user_id": user_id})
    new_version = (current_doc.get("version", 1) + 1) if current_doc else 2

    update_doc = {
        "version": new_version,
        "thresholds": {"suspicious": susp, "spam": spam},
        "group_caps": data.get("group_caps", {}),
        "rules": data.get("rules", {}),
        "keyword_categories": data.get("keyword_categories", []),
        "lists": data.get("lists", {}),
        "custom_rules": data.get("custom_rules", [])[:50],
        "updated_at": datetime.datetime.now(datetime.timezone.utc)
    }

    rule_configs_col().update_one(
        {"user_id": user_id},
        {"$set": update_doc},
        upsert=True
    )

    return jsonify({
        "ok": True,
        "data": {
            "version": new_version,
            "message": "Rule configuration updated successfully."
        }
    })

@rules_bp.route("/reset", methods=["POST"])
@login_required
def reset_rules_api():
    user_id = ObjectId(current_user.id)
    default_cfg = get_default_rule_config()
    
    current_doc = rule_configs_col().find_one({"user_id": user_id})
    new_version = (current_doc.get("version", 1) + 1) if current_doc else 2
    
    default_cfg["user_id"] = user_id
    default_cfg["version"] = new_version
    default_cfg["updated_at"] = datetime.datetime.now(datetime.timezone.utc)

    rule_configs_col().replace_one({"user_id": user_id}, default_cfg, upsert=True)
    default_cfg["_id"] = str(current_doc["_id"]) if current_doc else ""
    default_cfg["user_id"] = str(user_id)

    return jsonify({
        "ok": True,
        "data": {
            "version": new_version,
            "config": default_cfg,
            "message": "Reset all rules to system defaults."
        }
    })

@rules_bp.route("/test", methods=["POST"])
@login_required
def test_rules_sandbox():
    data = request.get_json() or {}
    mail_data = data.get("mail", {})
    cfg_override = data.get("config")

    user_id = ObjectId(current_user.id)
    if not cfg_override:
        cfg_override = rule_configs_col().find_one({"user_id": user_id}) or get_default_rule_config()

    parsed = to_parsed_email(mail_data)
    scan_res = scan_email(parsed, cfg_override)

    return jsonify({
        "ok": True,
        "data": {
            "score": scan_res.score,
            "label": scan_res.label,
            "thresholds": scan_res.thresholds,
            "group_scores": scan_res.group_scores,
            "reasons": [
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
        }
    })

@rules_bp.route("/export", methods=["GET"])
@login_required
def export_rules():
    user_id = ObjectId(current_user.id)
    cfg = rule_configs_col().find_one({"user_id": user_id}) or get_default_rule_config()
    cfg.pop("_id", None)
    cfg.pop("user_id", None)
    return Response(
        json.dumps(cfg, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=mailshield_rules_config.json"}
    )

@rules_bp.route("/import", methods=["POST"])
@login_required
def import_rules():
    user_id = ObjectId(current_user.id)
    data = request.get_json() or {}

    if not isinstance(data.get("rules"), dict) or not isinstance(data.get("thresholds"), dict):
        return jsonify({"ok": False, "error": {"code": "invalid_format", "message": "Invalid rule configuration JSON format."}}), 400

    current_doc = rule_configs_col().find_one({"user_id": user_id})
    new_version = (current_doc.get("version", 1) + 1) if current_doc else 2

    data["user_id"] = user_id
    data["version"] = new_version
    data["updated_at"] = datetime.datetime.now(datetime.timezone.utc)

    rule_configs_col().replace_one({"user_id": user_id}, data, upsert=True)
    return jsonify({"ok": True, "data": {"version": new_version, "message": "Imported rule configuration successfully."}})

@rules_bp.route("/lists", methods=["POST"])
@login_required
def add_to_list():
    data = request.get_json() or {}
    list_name = data.get("list") # "allow_senders", "allow_domains", "block_senders", "block_domains"
    value = data.get("value", "").strip().lower()

    if list_name not in ("allow_senders", "allow_domains", "block_senders", "block_domains", "extra_brands") or not value:
        return jsonify({"ok": False, "error": {"code": "invalid_input", "message": "Invalid list or value."}}), 400

    user_id = ObjectId(current_user.id)
    rule_configs_col().update_one(
        {"user_id": user_id},
        {"$addToSet": {f"lists.{list_name}": value}}
    )
    return jsonify({"ok": True, "data": {"message": f"Added '{value}' to {list_name}."}})
