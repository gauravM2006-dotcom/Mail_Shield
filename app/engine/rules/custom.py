import re
from typing import List, Dict, Any
from ..models import ParsedEmail, Reason

def is_safe_regex(pattern: str) -> bool:
    """Validate regex pattern safety against ReDoS (nested quantifiers)."""
    if len(pattern) > 200:
        return False
    # Check for catastrophic backtracking patterns like (a+)+ or (x*)*
    if re.search(r'\([^)]*[\+\*][^)]*\)[\+\*]', pattern):
        return False
    try:
        re.compile(pattern)
        return True
    except re.error:
        return False

def check(mail: ParsedEmail, cfg: Dict[str, Any]) -> List[Reason]:
    reasons: List[Reason] = []
    custom_rules = cfg.get("custom_rules", [])

    for idx, rule in enumerate(custom_rules[:50]): # limit to 50 rules
        if not rule.get("enabled", True):
            continue

        rule_id = rule.get("id", f"R-CUS-{idx+1:02d}")
        name = rule.get("name", "Custom Rule")
        field = rule.get("field", "subject").lower()
        match_type = rule.get("match_type", "contains").lower()
        pattern_str = rule.get("pattern", "")
        points = int(rule.get("points", 10))

        if not pattern_str:
            continue

        # Extract target text from ParsedEmail based on field
        target_texts: List[str] = []
        if field == "subject":
            target_texts = [mail.subject_raw[:20000]]
        elif field == "body":
            target_texts = [mail.body_raw[:20000]]
        elif field == "sender_address":
            target_texts = [mail.from_address]
        elif field == "sender_domain":
            target_texts = [mail.from_domain]
        elif field == "url_host":
            target_texts = [u.host for u in mail.urls]
        elif field == "attachment_name":
            target_texts = [a.name for a in mail.attachments]
        else:
            target_texts = [mail.subject_raw, mail.body_raw]

        matched = False
        evidence = ""

        for text in target_texts:
            if match_type == "contains":
                if pattern_str.lower() in text.lower():
                    matched = True
                    evidence = pattern_str
                    break
            elif match_type == "exact":
                if pattern_str.lower() == text.strip().lower():
                    matched = True
                    evidence = text.strip()
                    break
            elif match_type == "regex":
                if is_safe_regex(pattern_str):
                    try:
                        compiled = re.compile(pattern_str, re.IGNORECASE)
                        m = compiled.search(text)
                        if m:
                            matched = True
                            evidence = m.group(0)[:60]
                            break
                    except Exception:
                        pass

        if matched:
            reasons.append(Reason(
                rule_id=rule_id,
                group="CUS",
                title=f"Custom: {name}",
                explanation=f"Triggered user-defined custom rule matching '{pattern_str}' in {field}.",
                evidence=evidence or pattern_str,
                points=points
            ))

    return reasons
