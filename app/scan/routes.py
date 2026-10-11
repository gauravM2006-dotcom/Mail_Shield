import datetime
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from bson import ObjectId
from ..db import emails_col, scans_col, scan_batches_col, rule_configs_col, mail_accounts_col
from ..engine import to_parsed_email, scan_email
from .batch_runner import run_scan_single, run_batch_scan

scan_bp = Blueprint("scan", __name__)

@scan_bp.route("/scan-all", methods=["GET"])
@login_required
def scan_all_page():
    return render_template("pages/scan_all.html")

@scan_bp.route("/manual-scan", methods=["GET"])
@login_required
def manual_scan_page():
    return render_template("pages/manual_scan.html")

@scan_bp.route("/single", methods=["POST"])
@login_required
def scan_single_api():
    data = request.get_json() or {}
    email_id = data.get("email_id")
    if not email_id:
        return jsonify({"ok": False, "error": {"code": "missing_id", "message": "email_id is required."}}), 400

    try:
        e_oid = ObjectId(email_id)
    except Exception:
        return jsonify({"ok": False, "error": {"code": "invalid_id", "message": "Invalid email_id format."}}), 400

    user_id = ObjectId(current_user.id)
    result = run_scan_single(e_oid, user_id)
    if not result:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "Email not found."}}), 404

    return jsonify({"ok": True, "data": result})

@scan_bp.route("/selected", methods=["POST"])
@login_required
def scan_selected_api():
    data = request.get_json() or {}
    provider = data.get("provider")
    email_ids = data.get("email_ids", [])

    if not email_ids:
        return jsonify({"ok": False, "error": {"code": "empty_selection", "message": "No emails selected."}}), 400

    user_id = ObjectId(current_user.id)
    valid_oids = []
    for raw_id in email_ids:
        try:
            valid_oids.append(ObjectId(raw_id))
        except Exception:
            pass

    batch_doc = {
        "user_id": user_id,
        "scope": "selected",
        "providers": [provider] if provider else [],
        "status": "running",
        "totals": {"total": len(valid_oids), "done": 0, "safe": 0, "suspicious": 0, "spam": 0},
        "started_at": datetime.datetime.now(datetime.timezone.utc),
        "finished_at": None
    }
    batch_ins = scan_batches_col().insert_one(batch_doc)
    batch_id = batch_ins.inserted_id

    # Run batch
    totals = run_batch_scan(batch_id, user_id, valid_oids)
    return jsonify({
        "ok": True,
        "data": {
            "batch_id": str(batch_id),
            "totals": totals,
            "message": f"Successfully scanned {totals['done']} selected messages."
        }
    }), 202

@scan_bp.route("/tab", methods=["POST"])
@login_required
def scan_tab_api():
    data = request.get_json() or {}
    provider = data.get("provider")
    mode = data.get("mode", "unscanned") # "unscanned" | "all" | "outdated"

    user_id = ObjectId(current_user.id)
    query: dict = {"user_id": user_id, "provider": provider}
    if mode == "unscanned":
        query["current_scan"] = None

    cursor = emails_col().find(query, {"_id": 1})
    email_ids = [doc["_id"] for doc in cursor]

    if not email_ids:
        return jsonify({"ok": True, "data": {"message": "No matching emails to scan.", "totals": {"total": 0, "done": 0}}})

    batch_doc = {
        "user_id": user_id,
        "scope": "tab",
        "providers": [provider],
        "status": "running",
        "totals": {"total": len(email_ids), "done": 0, "safe": 0, "suspicious": 0, "spam": 0},
        "started_at": datetime.datetime.now(datetime.timezone.utc),
        "finished_at": None
    }
    batch_ins = scan_batches_col().insert_one(batch_doc)
    batch_id = batch_ins.inserted_id

    totals = run_batch_scan(batch_id, user_id, email_ids)
    return jsonify({
        "ok": True,
        "data": {
            "batch_id": str(batch_id),
            "totals": totals,
            "message": f"Scanned {totals['done']} messages in {provider.capitalize()} tab."
        }
    }), 202

@scan_bp.route("/all", methods=["POST"])
@login_required
def scan_all_api():
    data = request.get_json() or {}
    mode = data.get("mode", "unscanned")
    providers = data.get("providers", ["gmail", "outlook", "yahoo", "icloud"])

    user_id = ObjectId(current_user.id)
    query: dict = {"user_id": user_id, "provider": {"$in": providers}}
    if mode == "unscanned":
        query["current_scan"] = None

    cursor = emails_col().find(query, {"_id": 1})
    email_ids = [doc["_id"] for doc in cursor]

    if not email_ids:
        return jsonify({"ok": True, "data": {"message": "All mailboxes are already scanned.", "totals": {"total": 0, "done": 0}}})

    batch_doc = {
        "user_id": user_id,
        "scope": "all",
        "providers": providers,
        "status": "running",
        "totals": {"total": len(email_ids), "done": 0, "safe": 0, "suspicious": 0, "spam": 0},
        "started_at": datetime.datetime.now(datetime.timezone.utc),
        "finished_at": None
    }
    batch_ins = scan_batches_col().insert_one(batch_doc)
    batch_id = batch_ins.inserted_id

    totals = run_batch_scan(batch_id, user_id, email_ids)
    return jsonify({
        "ok": True,
        "data": {
            "batch_id": str(batch_id),
            "totals": totals,
            "message": f"Completed scanning across all mailboxes. Scanned {totals['done']} messages."
        }
    }), 202

@scan_bp.route("/manual", methods=["POST"])
@login_required
def scan_manual_api():
    data = request.get_json() or {}
    from_name = data.get("from_name", "")
    from_address = data.get("from_address", "")
    reply_to = data.get("reply_to", "")
    subject = data.get("subject", "")
    body = data.get("body", "")
    urls_input = data.get("urls", [])
    attachments_input = data.get("attachments", [])
    auth_input = data.get("auth", {})
    save_to_history = data.get("save", True)

    urls = []
    if isinstance(urls_input, str):
        urls = [u.strip() for u in urls_input.splitlines() if u.strip()]
    elif isinstance(urls_input, list):
        urls = urls_input

    attachments = []
    if isinstance(attachments_input, str):
        attachments = [{"name": a.strip()} for a in attachments_input.splitlines() if a.strip()]
    elif isinstance(attachments_input, list):
        attachments = attachments_input

    mail_payload = {
        "from": {"name": from_name, "address": from_address},
        "reply_to": {"name": "", "address": reply_to},
        "subject": subject,
        "body_text": body,
        "urls": urls,
        "attachments": attachments,
        "auth_results": auth_input
    }

    user_id = ObjectId(current_user.id)
    rule_cfg = rule_configs_col().find_one({"user_id": user_id}) or {}
    parsed = to_parsed_email(mail_payload)
    scan_res = scan_email(parsed, rule_cfg)

    now = datetime.datetime.now(datetime.timezone.utc)
    scan_id = None
    if save_to_history:
        scan_doc = {
            "user_id": user_id,
            "account_id": None,
            "batch_id": None,
            "email_id": None,
            "source": "manual",
            "provider": "manual",
            "email_summary": {
                "from": mail_payload["from"],
                "subject": subject,
                "received_at": now
            },
            "score": scan_res.score,
            "label": scan_res.label,
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
            ],
            "group_scores": scan_res.group_scores,
            "thresholds": scan_res.thresholds,
            "rules_version": scan_res.rules_version,
            "created_at": now
        }
        ins = scans_col().insert_one(scan_doc)
        scan_id = str(ins.inserted_id)

    return jsonify({
        "ok": True,
        "data": {
            "scan_id": scan_id,
            "score": scan_res.score,
            "label": scan_res.label,
            "thresholds": scan_res.thresholds,
            "group_scores": scan_res.group_scores,
            "rules_version": scan_res.rules_version,
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

@scan_bp.route("/batches/<batch_id>", methods=["GET"])
@login_required
def get_batch_status(batch_id):
    user_id = ObjectId(current_user.id)
    try:
        b_oid = ObjectId(batch_id)
    except Exception:
        return jsonify({"ok": False, "error": {"code": "invalid_id", "message": "Invalid batch ID."}}), 400

    doc = scan_batches_col().find_one({"_id": b_oid, "user_id": user_id})
    if not doc:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "Batch not found."}}), 404

    return jsonify({
        "ok": True,
        "data": {
            "batch_id": str(doc["_id"]),
            "scope": doc.get("scope"),
            "status": doc.get("status"),
            "totals": doc.get("totals", {}),
            "per_provider": doc.get("per_provider", {}),
            "started_at": doc.get("started_at").isoformat() + "Z" if doc.get("started_at") else None,
            "finished_at": doc.get("finished_at").isoformat() + "Z" if doc.get("finished_at") else None
        }
    })

@scan_bp.route("/batches/<batch_id>/cancel", methods=["POST"])
@login_required
def cancel_batch(batch_id):
    user_id = ObjectId(current_user.id)
    try:
        b_oid = ObjectId(batch_id)
    except Exception:
        return jsonify({"ok": False, "error": {"code": "invalid_id", "message": "Invalid batch ID."}}), 400

    scan_batches_col().update_one({"_id": b_oid, "user_id": user_id}, {"$set": {"status": "cancelled"}})
    return jsonify({"ok": True, "data": {"message": "Batch cancellation requested."}})
