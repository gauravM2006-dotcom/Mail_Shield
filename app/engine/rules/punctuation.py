import re
from typing import List, Dict, Any
from ..models import ParsedEmail, Reason

def check(mail: ParsedEmail, cfg: Dict[str, Any]) -> List[Reason]:
    reasons: List[Reason] = []
    rules_cfg = cfg.get("rules", {})

    def rule_meta(rule_id: str, default_pts: int):
        r = rules_cfg.get(rule_id, {})
        return r.get("enabled", True), r.get("points", default_pts)

    # R-PUN-01: Repeated ! or ? (3 or more in subject = 5 pts, or at least two runs in body = 3 pts)
    en_r01, pts_r01 = rule_meta("R-PUN-01", 5)
    if en_r01:
        # Check subject
        subj_matches = re.findall(r'[!?]{3,}', mail.subject_raw)
        if subj_matches:
            reasons.append(Reason(
                rule_id="R-PUN-01",
                group="PUN",
                title="Repeated Exclamation / Question Marks in Subject",
                explanation=f"Subject uses repetitive punctuation ('{subj_matches[0]}') to create exaggerated urgency.",
                evidence=subj_matches[0],
                points=pts_r01
            ))
        else:
            # Check body: at least 2 runs of 3+ marks
            body_matches = re.findall(r'[!?]{3,}', mail.body_raw)
            if len(body_matches) >= 2:
                reasons.append(Reason(
                    rule_id="R-PUN-01",
                    group="PUN",
                    title="Repeated Punctuation in Body",
                    explanation="Email body contains multiple runs of repeated exclamation or question marks.",
                    evidence=", ".join(body_matches[:3]),
                    points=max(1, pts_r01 - 2)
                ))

    # R-PUN-02: Currency Symbol Abuse (3 or more $, €, £, ₹ in a row)
    en_r02, pts_r02 = rule_meta("R-PUN-02", 4)
    if en_r02:
        combined = f"{mail.subject_raw} {mail.body_raw}"
        curr_matches = re.findall(r'[\$€£₹]{3,}', combined)
        if curr_matches:
            reasons.append(Reason(
                rule_id="R-PUN-02",
                group="PUN",
                title="Excessive Currency Symbols",
                explanation="Detected runs of repeated currency symbols ('$$$') typical of financial scam emails.",
                evidence=curr_matches[0],
                points=pts_r02
            ))

    return reasons
