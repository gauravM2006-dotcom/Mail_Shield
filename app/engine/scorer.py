from dataclasses import dataclass, field
from typing import Dict, Any, List
from .models import ParsedEmail, Reason, ScanResult
from .rules import (
    keywords,
    sender,
    urls,
    caps,
    punctuation,
    attachments,
    custom,
    combos,
    lists
)

DEFAULT_GROUP_CAPS = {
    "KW": 40,
    "SND": 45,
    "URL": 50,
    "CAP": 14,
    "PUN": 9,
    "ATT": 60,
    "CMB": 20,
    "CUS": 50
}

GROUPS = [
    ("KW", keywords.check),
    ("SND", sender.check),
    ("URL", urls.check),
    ("CAP", caps.check),
    ("PUN", punctuation.check),
    ("ATT", attachments.check),
    ("CUS", custom.check)
]

def classify(score: int, thresholds: Dict[str, int]) -> str:
    """Classify risk score into 'safe', 'suspicious', or 'spam'."""
    spam_th = thresholds.get("spam", 60)
    susp_th = thresholds.get("suspicious", 30)
    
    if score >= spam_th:
        return "spam"
    if score >= susp_th:
        return "suspicious"
    return "safe"

def scan_email(mail: ParsedEmail, cfg: Dict[str, Any]) -> ScanResult:
    """
    Deterministic rule engine scanner.
    Pure Python function: input ParsedEmail + config dictionary -> ScanResult.
    """
    reasons: List[Reason] = []
    group_scores: Dict[str, int] = {}
    
    rules_cfg = cfg.get("rules", {})
    group_caps = dict(DEFAULT_GROUP_CAPS)
    group_caps.update(cfg.get("group_caps", {}))

    # Evaluate standard groups
    for group_code, check_fn in GROUPS:
        found = check_fn(mail, cfg)
        # Filter enabled rules
        enabled_reasons = []
        for r in found:
            rule_entry = rules_cfg.get(r.rule_id, {})
            if rule_entry.get("enabled", True):
                enabled_reasons.append(r)
                
        reasons.extend(enabled_reasons)
        group_total = sum(r.points for r in enabled_reasons)
        group_scores[group_code] = min(max(0, group_total), group_caps.get(group_code, 100))

    # Evaluate compound and contextual rules
    extra_reasons = combos.check(mail, cfg, reasons)
    enabled_extra = [
        r for r in extra_reasons 
        if rules_cfg.get(r.rule_id, {}).get("enabled", True)
    ]
    reasons.extend(enabled_extra)
    group_scores["CMB"] = min(
        max(0, sum(r.points for r in enabled_extra)),
        group_caps.get("CMB", 20)
    )

    # Initial aggregate score capped at 100
    raw_total = sum(group_scores.values())
    score = min(100, max(0, raw_total))

    # Apply Allow-list and Block-list overrides
    score = lists.apply(mail, cfg, reasons, group_scores, score)
    score = min(100, max(0, score))

    thresholds = cfg.get("thresholds", {"suspicious": 30, "spam": 60})
    label = classify(score, thresholds)
    rules_version = cfg.get("version", 1)

    # Sort reasons by descending points
    reasons.sort(key=lambda r: abs(r.points), reverse=True)

    return ScanResult(
        score=score,
        label=label,
        reasons=reasons,
        group_scores=group_scores,
        rules_version=rules_version,
        thresholds=thresholds
    )
