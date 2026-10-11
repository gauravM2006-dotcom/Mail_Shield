from typing import List, Dict, Any
from ..models import ParsedEmail, Reason

def apply(mail: ParsedEmail, cfg: Dict[str, Any], reasons: List[Reason], group_scores: Dict[str, int], current_score: int) -> int:
    lists_cfg = cfg.get("lists", {})
    allow_senders = {s.strip().lower() for s in lists_cfg.get("allow_senders", []) if s.strip()}
    allow_domains = {d.strip().lower() for d in lists_cfg.get("allow_domains", []) if d.strip()}
    block_senders = {s.strip().lower() for s in lists_cfg.get("block_senders", []) if s.strip()}
    block_domains = {d.strip().lower() for d in lists_cfg.get("block_domains", []) if d.strip()}

    sender_addr = mail.from_address.lower()
    sender_dom = mail.from_domain.lower()
    sender_reg = mail.from_registrable.lower()

    # 1. Check Block-List (Highest Priority)
    is_blocked = (sender_addr in block_senders or 
                  sender_dom in block_domains or 
                  sender_reg in block_domains)

    if is_blocked:
        reasons.insert(0, Reason(
            rule_id="R-LST-BLOCK",
            group="LST",
            title="Blocked Sender",
            explanation="Sender address or domain is present in your personal block-list.",
            evidence=f"{mail.from_address} (blocked)",
            points=100
        ))
        group_scores["LST"] = 100
        return 100

    # 2. Check Allow-List
    is_allowed = (sender_addr in allow_senders or 
                  sender_dom in allow_domains or 
                  sender_reg in allow_domains)

    if is_allowed:
        # Check if dangerous attachments are present (R-ATT-01 or R-ATT-02)
        has_dangerous_att = any(r.rule_id in ("R-ATT-01", "R-ATT-02") for r in reasons)
        if has_dangerous_att:
            reasons.insert(0, Reason(
                rule_id="R-LST-ALLOW-OVERRIDE",
                group="LST",
                title="Allow-List Overridden by Dangerous Attachment",
                explanation="Sender is in your allow-list, but the message carries a high-risk executable attachment.",
                evidence=f"{mail.from_address} (allow-listed with dangerous attachment)",
                points=0
            ))
            # Dangerous attachment points still count
            return current_score
        else:
            reasons.insert(0, Reason(
                rule_id="R-LST-ALLOW",
                group="LST",
                title="Trusted Sender",
                explanation="Sender address or domain is present in your personal allow-list.",
                evidence=f"{mail.from_address} (trusted)",
                points=0
            ))
            # Zero out other points
            return 0

    return current_score
