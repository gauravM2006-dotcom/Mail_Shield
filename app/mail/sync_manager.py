import datetime
from bson import ObjectId
from typing import Dict, Any, Optional, List
from flask import current_app
from ..db import mail_accounts_col, emails_col, user_settings_col, rule_configs_col, scans_col
from ..security import decrypt_data
from ..engine import to_parsed_email, scan_email
from .providers.mock import MockMailProvider
from .providers.gmail import GmailProvider

def get_provider_adapter(account_doc: Dict[str, Any]):
    """Instantiate the appropriate provider adapter for an account document."""
    provider_key = account_doc.get("provider", "mock")
    if provider_key == "gmail":
        return GmailProvider(account_doc)
    return MockMailProvider(account_doc)

def upsert_email(account_doc: Dict[str, Any], raw_msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Save normalized mail to emails collection and perform auto-scan if configured."""
    user_id = account_doc["user_id"]
    account_id = account_doc["_id"]
    provider = account_doc["provider"]
    provider_msg_id = raw_msg.get("provider_msg_id", "")

    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Parse received_at
    rec_at = raw_msg.get("received_at")
    if isinstance(rec_at, str):
        try:
            rec_dt = datetime.datetime.fromisoformat(rec_at.replace("Z", "+00:00"))
        except Exception:
            rec_dt = now
    elif isinstance(rec_at, datetime.datetime):
        rec_dt = rec_at
    else:
        rec_dt = now

    doc = {
        "user_id": user_id,
        "account_id": account_id,
        "provider": provider,
        "provider_msg_id": provider_msg_id,
        "message_id_header": raw_msg.get("message_id_header", ""),
        "from": raw_msg.get("from", {}),
        "to": raw_msg.get("to", []),
        "reply_to": raw_msg.get("reply_to", {}),
        "subject": raw_msg.get("subject", "(No Subject)"),
        "snippet": raw_msg.get("snippet", "")[:200],
        "body_text": raw_msg.get("body_text", "")[:200000],
        "urls": raw_msg.get("urls", []),
        "attachments": raw_msg.get("attachments", []),
        "auth_results": raw_msg.get("auth_results", {}),
        "received_at": rec_dt,
        "is_read": raw_msg.get("is_read", False),
        "folder": "inbox",
        "created_at": now
    }

    # Check auto-scan preferences
    settings = user_settings_col().find_one({"user_id": user_id}) or {}
    sync_settings = settings.get("sync", {})
    auto_scan_on = sync_settings.get("auto_scan_all", False) or sync_settings.get("auto_scan_providers", {}).get(provider, False)

    if auto_scan_on:
        rule_cfg = rule_configs_col().find_one({"user_id": user_id}) or {}
        parsed = to_parsed_email(doc)
        scan_res = scan_email(parsed, rule_cfg)
        
        # Save scan document
        scan_doc = {
            "user_id": user_id,
            "account_id": account_id,
            "batch_id": None,
            "email_id": None, # updated after insert
            "source": "mailbox",
            "provider": provider,
            "email_summary": {
                "from": doc["from"],
                "subject": doc["subject"],
                "received_at": doc["received_at"]
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
        
        doc["current_scan"] = {
            "scan_id": scan_ins.inserted_id,
            "label": scan_res.label,
            "score": scan_res.score,
            "rules_version": scan_res.rules_version,
            "scanned_at": now
        }
    else:
        doc["current_scan"] = None

    # Upsert with unique index (account_id, provider_msg_id)
    res = emails_col().update_one(
        {"account_id": account_id, "provider_msg_id": provider_msg_id},
        {"$setOnInsert": doc},
        upsert=True
    )
    
    saved_doc = emails_col().find_one({"account_id": account_id, "provider_msg_id": provider_msg_id})
    return saved_doc

def run_initial_sync(account_id: ObjectId, depth_days: int = 30) -> int:
    """Execute initial mailbox synchronization."""
    acc = mail_accounts_col().find_one({"_id": account_id})
    if not acc:
        return 0

    mail_accounts_col().update_one(
        {"_id": account_id},
        {
            "$set": {
                "status": "syncing",
                "initial_sync": {
                    "state": "running",
                    "total": 0,
                    "done": 0,
                    "depth_days": depth_days,
                    "started_at": datetime.datetime.now(datetime.timezone.utc)
                }
            }
        }
    )

    adapter = get_provider_adapter(acc)
    msg_ids, _ = adapter.list_page(since_days=depth_days, cursor=None, limit=50)

    total_synced = 0
    for m_id in msg_ids:
        raw_msg = adapter.get_message(m_id)
        if raw_msg:
            upsert_email(acc, raw_msg)
            total_synced += 1

    mail_accounts_col().update_one(
        {"_id": account_id},
        {
            "$set": {
                "status": "live",
                "last_sync_at": datetime.datetime.now(datetime.timezone.utc),
                "initial_sync.state": "done",
                "initial_sync.done": total_synced,
                "initial_sync.total": total_synced,
                "initial_sync.finished_at": datetime.datetime.now(datetime.timezone.utc)
            }
        }
    )
    return total_synced
