import datetime
from bson import ObjectId
from typing import List, Dict, Any, Optional
from ..db import emails_col, scans_col, scan_batches_col, rule_configs_col
from ..engine import to_parsed_email, scan_email

def run_scan_single(email_id: ObjectId, user_id: ObjectId) -> Optional[Dict[str, Any]]:
    """Scan a single mail synchronously and return the result."""
    email_doc = emails_col().find_one({"_id": email_id, "user_id": user_id})
    if not email_doc:
        return None

    rule_cfg = rule_configs_col().find_one({"user_id": user_id}) or {}
    parsed = to_parsed_email(email_doc)
    scan_res = scan_email(parsed, rule_cfg)

    now = datetime.datetime.now(datetime.timezone.utc)
    scan_doc = {
        "user_id": user_id,
        "account_id": email_doc.get("account_id"),
        "batch_id": None,
        "email_id": email_id,
        "source": "mailbox",
        "provider": email_doc.get("provider"),
        "email_summary": {
            "from": email_doc.get("from"),
            "subject": email_doc.get("subject"),
            "received_at": email_doc.get("received_at")
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

    scan_ins = scans_col().insert_one(scan_doc)
    scan_id = scan_ins.inserted_id

    # Update denormalized current_scan on emails
    current_scan_entry = {
        "scan_id": scan_id,
        "label": scan_res.label,
        "score": scan_res.score,
        "rules_version": scan_res.rules_version,
        "scanned_at": now
    }
    emails_col().update_one({"_id": email_id}, {"$set": {"current_scan": current_scan_entry}})

    return {
        "scan_id": str(scan_id),
        "email_id": str(email_id),
        "score": scan_res.score,
        "label": scan_res.label,
        "thresholds": scan_res.thresholds,
        "group_scores": scan_res.group_scores,
        "rules_version": scan_res.rules_version,
        "reasons": scan_doc["reasons"]
    }

def run_batch_scan(batch_id: ObjectId, user_id: ObjectId, email_ids: List[ObjectId]) -> Dict[str, Any]:
    """Execute batch scanning over a list of email IDs."""
    rule_cfg = rule_configs_col().find_one({"user_id": user_id}) or {}
    
    scan_batches_col().update_one(
        {"_id": batch_id},
        {"$set": {"status": "running", "started_at": datetime.datetime.now(datetime.timezone.utc)}}
    )

    totals = {"total": len(email_ids), "done": 0, "safe": 0, "suspicious": 0, "spam": 0}
    per_provider = {}

    for e_id in email_ids:
        # Check if cancelled
        batch_doc = scan_batches_col().find_one({"_id": batch_id})
        if batch_doc and batch_doc.get("status") == "cancelled":
            break

        email_doc = emails_col().find_one({"_id": e_id, "user_id": user_id})
        if not email_doc:
            continue

        prov = email_doc.get("provider", "unknown")
        if prov not in per_provider:
            per_provider[prov] = {"total": 0, "safe": 0, "suspicious": 0, "spam": 0}

        parsed = to_parsed_email(email_doc)
        scan_res = scan_email(parsed, rule_cfg)
        now = datetime.datetime.now(datetime.timezone.utc)

        scan_doc = {
            "user_id": user_id,
            "account_id": email_doc.get("account_id"),
            "batch_id": batch_id,
            "email_id": e_id,
            "source": "mailbox",
            "provider": prov,
            "email_summary": {
                "from": email_doc.get("from"),
                "subject": email_doc.get("subject"),
                "received_at": email_doc.get("received_at")
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
        scan_ins = scans_col().insert_one(scan_doc)

        current_scan_entry = {
            "scan_id": scan_ins.inserted_id,
            "label": scan_res.label,
            "score": scan_res.score,
            "rules_version": scan_res.rules_version,
            "scanned_at": now
        }
        emails_col().update_one({"_id": e_id}, {"$set": {"current_scan": current_scan_entry}})

        totals["done"] += 1
        totals[scan_res.label] += 1
        per_provider[prov]["total"] += 1
        per_provider[prov][scan_res.label] += 1

        scan_batches_col().update_one(
            {"_id": batch_id},
            {"$set": {"totals": totals, "per_provider": per_provider}}
        )

    scan_batches_col().update_one(
        {"_id": batch_id},
        {"$set": {
            "status": "completed",
            "finished_at": datetime.datetime.now(datetime.timezone.utc),
            "totals": totals,
            "per_provider": per_provider
        }}
    )
    return totals
