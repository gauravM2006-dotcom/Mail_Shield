import csv
import io
import json
from flask import Blueprint, render_template, request, jsonify, Response
from flask_login import login_required, current_user
from bson import ObjectId
from ..db import scans_col, scan_batches_col

history_bp = Blueprint("history", __name__)

@history_bp.route("/history", methods=["GET"])
@login_required
def history_page():
    return render_template("pages/history.html")

@history_bp.route("/batches", methods=["GET"])
@login_required
def list_batches():
    user_id = ObjectId(current_user.id)
    batches = list(scan_batches_col().find({"user_id": user_id}).sort([("started_at", -1)]).limit(50))
    
    result = []
    for b in batches:
        result.append({
            "id": str(b["_id"]),
            "scope": b.get("scope"),
            "providers": b.get("providers", []),
            "status": b.get("status"),
            "totals": b.get("totals", {}),
            "started_at": b.get("started_at").isoformat() + "Z" if b.get("started_at") else None,
            "finished_at": b.get("finished_at").isoformat() + "Z" if b.get("finished_at") else None
        })
    return jsonify({"ok": True, "data": result})

@history_bp.route("/scans", methods=["GET"])
@login_required
def list_scans():
    user_id = ObjectId(current_user.id)
    query: dict = {"user_id": user_id}

    provider = request.args.get("provider")
    if provider and provider != "all":
        query["provider"] = provider

    label = request.args.get("label")
    if label and label in ("safe", "suspicious", "spam"):
        query["label"] = label

    q = request.args.get("q", "").strip()
    if q:
        query["$or"] = [
            {"email_summary.subject": {"$regex": q, "$options": "i"}},
            {"email_summary.from.address": {"$regex": q, "$options": "i"}},
            {"email_summary.from.name": {"$regex": q, "$options": "i"}}
        ]

    limit = min(100, int(request.args.get("limit", 50)))
    total = scans_col().count_documents(query)
    cursor = scans_col().find(query).sort([("created_at", -1)]).limit(limit)

    items = []
    for doc in cursor:
        items.append({
            "id": str(doc["_id"]),
            "provider": doc.get("provider"),
            "source": doc.get("source"),
            "email_summary": doc.get("email_summary"),
            "score": doc.get("score"),
            "label": doc.get("label"),
            "reasons_count": len(doc.get("reasons", [])),
            "created_at": doc.get("created_at").isoformat() + "Z" if doc.get("created_at") else None
        })

    return jsonify({"ok": True, "data": {"items": items, "total": total, "limit": limit}})

@history_bp.route("/scans/<scan_id>", methods=["GET"])
@login_required
def get_scan(scan_id):
    user_id = ObjectId(current_user.id)
    try:
        s_oid = ObjectId(scan_id)
    except Exception:
        return jsonify({"ok": False, "error": {"code": "invalid_id", "message": "Invalid scan ID."}}), 400

    doc = scans_col().find_one({"_id": s_oid, "user_id": user_id})
    if not doc:
        return jsonify({"ok": False, "error": {"code": "not_found", "message": "Scan not found."}}), 404

    return jsonify({
        "ok": True,
        "data": {
            "id": str(doc["_id"]),
            "provider": doc.get("provider"),
            "source": doc.get("source"),
            "email_summary": doc.get("email_summary"),
            "score": doc.get("score"),
            "label": doc.get("label"),
            "reasons": doc.get("reasons", []),
            "group_scores": doc.get("group_scores", {}),
            "thresholds": doc.get("thresholds", {}),
            "rules_version": doc.get("rules_version"),
            "created_at": doc.get("created_at").isoformat() + "Z" if doc.get("created_at") else None
        }
    })

@history_bp.route("/export", methods=["GET"])
@login_required
def export_history():
    user_id = ObjectId(current_user.id)
    fmt = request.args.get("format", "csv").lower()
    scans = list(scans_col().find({"user_id": user_id}).sort([("created_at", -1)]).limit(1000))

    if fmt == "json":
        data = []
        for s in scans:
            s["_id"] = str(s["_id"])
            if s.get("account_id"):
                s["account_id"] = str(s["account_id"])
            if s.get("batch_id"):
                s["batch_id"] = str(s["batch_id"])
            if s.get("email_id"):
                s["email_id"] = str(s["email_id"])
            if s.get("created_at"):
                s["created_at"] = s["created_at"].isoformat() + "Z"
            data.append(s)
        return Response(json.dumps(data, indent=2), mimetype="application/json", headers={"Content-Disposition": "attachment;filename=mailshield_scans.json"})

    # Default CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Scan ID", "Date (UTC)", "Provider", "From", "Subject", "Score", "Label", "Reasons Count"])
    for s in scans:
        date_str = s.get("created_at").isoformat() if s.get("created_at") else ""
        from_str = s.get("email_summary", {}).get("from", {}).get("address", "")
        subj_str = s.get("email_summary", {}).get("subject", "")
        writer.writerow([
            str(s["_id"]),
            date_str,
            s.get("provider", ""),
            from_str,
            subj_str,
            s.get("score", 0),
            s.get("label", ""),
            len(s.get("reasons", []))
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=mailshield_scans.csv"}
    )

@history_bp.route("/scans/<scan_id>", methods=["DELETE"])
@login_required
def delete_scan(scan_id):
    user_id = ObjectId(current_user.id)
    try:
        s_oid = ObjectId(scan_id)
    except Exception:
        return jsonify({"ok": False, "error": {"code": "invalid_id", "message": "Invalid scan ID."}}), 400

    scans_col().delete_one({"_id": s_oid, "user_id": user_id})
    return jsonify({"ok": True, "data": {"message": "Scan deleted."}})

@history_bp.route("/batches/<batch_id>", methods=["DELETE"])
@login_required
def delete_batch(batch_id):
    user_id = ObjectId(current_user.id)
    try:
        b_oid = ObjectId(batch_id)
    except Exception:
        return jsonify({"ok": False, "error": {"code": "invalid_id", "message": "Invalid batch ID."}}), 400

    scan_batches_col().delete_one({"_id": b_oid, "user_id": user_id})
    scans_col().delete_many({"batch_id": b_oid, "user_id": user_id})
    return jsonify({"ok": True, "data": {"message": "Batch and associated scans deleted."}})

@history_bp.route("", methods=["DELETE"])
@login_required
def clear_all_history():
    user_id = ObjectId(current_user.id)
    scans_col().delete_many({"user_id": user_id})
    scan_batches_col().delete_many({"user_id": user_id})
    return jsonify({"ok": True, "data": {"message": "All scan history cleared."}})
