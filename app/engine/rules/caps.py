import re
from typing import List, Dict, Any
from ..models import ParsedEmail, Reason

def check(mail: ParsedEmail, cfg: Dict[str, Any]) -> List[Reason]:
    reasons: List[Reason] = []
    rules_cfg = cfg.get("rules", {})

    def rule_meta(rule_id: str, default_pts: int):
        r = rules_cfg.get(rule_id, {})
        return r.get("enabled", True), r.get("points", default_pts)

    # R-CAP-01: Shouting Subject (> 50% uppercase, min 8 letters)
    en_r01, pts_r01 = rule_meta("R-CAP-01", 8)
    if en_r01 and mail.subject_raw:
        letters = [c for c in mail.subject_raw if c.isalpha()]
        if len(letters) >= 8:
            upper_count = sum(1 for c in letters if c.isupper())
            ratio = upper_count / len(letters)
            if ratio > 0.50:
                reasons.append(Reason(
                    rule_id="R-CAP-01",
                    group="CAP",
                    title="Excessive Subject Capitalization",
                    explanation=f"Subject contains {int(ratio*100)}% uppercase letters ('SHOUTING'), typical of aggressive spam.",
                    evidence=mail.subject_raw,
                    points=pts_r01
                ))

    # R-CAP-02: Shouting Body (> 35% uppercase, min 80 letters)
    en_r02, pts_r02 = rule_meta("R-CAP-02", 6)
    if en_r02 and mail.body_raw:
        body_letters = [c for c in mail.body_raw if c.isalpha()]
        if len(body_letters) >= 80:
            upper_count = sum(1 for c in body_letters if c.isupper())
            ratio = upper_count / len(body_letters)
            if ratio > 0.35:
                reasons.append(Reason(
                    rule_id="R-CAP-02",
                    group="CAP",
                    title="Excessive Body Capitalization",
                    explanation=f"Message body contains {int(ratio*100)}% uppercase letters.",
                    evidence=f"{int(ratio*100)}% uppercase characters",
                    points=pts_r02
                ))

    # R-CAP-03: Many CAPITAL Words (at least 5 words of 4+ letters in ALL CAPS)
    en_r03, pts_r03 = rule_meta("R-CAP-03", 4)
    if en_r03:
        combined = f"{mail.subject_raw} {mail.body_raw}"
        words = re.findall(r'\b[A-Z]{4,}\b', combined)
        # Exclude common acronyms like HTML, HTTP, HTTPS, DMARC, DKIM, etc.
        common_acronyms = {"HTML", "HTTP", "HTTPS", "DMARC", "DKIM", "SMTP", "IMAP", "JSON", "MIME", "IP"}
        shout_words = [w for w in words if w not in common_acronyms]
        if len(shout_words) >= 5:
            reasons.append(Reason(
                rule_id="R-CAP-03",
                group="CAP",
                title="Multiple ALL-CAPS Words",
                explanation=f"Found {len(shout_words)} capitalized words (4+ letters), creating artificial urgency.",
                evidence=", ".join(shout_words[:6]),
                points=pts_r03
            ))

    return reasons
