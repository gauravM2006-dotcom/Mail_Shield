from typing import List, Dict, Any, Set
from ..models import ParsedEmail, Reason

def check(mail: ParsedEmail, cfg: Dict[str, Any], existing_reasons: List[Reason]) -> List[Reason]:
    reasons: List[Reason] = []
    rules_cfg = cfg.get("rules", {})

    def rule_meta(rule_id: str, default_pts: int):
        r = rules_cfg.get(rule_id, {})
        return r.get("enabled", True), r.get("points", default_pts)

    matched_rule_ids = {r.rule_id for r in existing_reasons}

    # R-GEN-01: Empty subject with link
    en_gen01, pts_gen01 = rule_meta("R-GEN-01", 4)
    if en_gen01 and not mail.subject.strip() and len(mail.urls) > 0:
        reasons.append(Reason(
            rule_id="R-GEN-01",
            group="CMB",
            title="Missing Subject with Embedded Links",
            explanation="The email has no subject line but contains outbound links, a pattern typical of automated spam.",
            evidence=f"No subject; {len(mail.urls)} link(s)",
            points=pts_gen01
        ))

    # R-GEN-02: Link-only message (body shorter than 40 characters and contains a link)
    en_gen02, pts_gen02 = rule_meta("R-GEN-02", 5)
    if en_gen02 and len(mail.body.strip()) < 40 and len(mail.urls) > 0:
        reasons.append(Reason(
            rule_id="R-GEN-02",
            group="CMB",
            title="Link-Only Sparse Message",
            explanation="The email body contains almost no message text other than an outbound destination link.",
            evidence=f"Body length: {len(mail.body.strip())} chars with links",
            points=pts_gen02
        ))

    # R-CMB-01: Urgency + Risky Link
    en_cmb01, pts_cmb01 = rule_meta("R-CMB-01", 10)
    has_urgency = "R-KW-03" in matched_rule_ids
    has_risky_link = any(r in matched_rule_ids for r in ("R-URL-01", "R-URL-02", "R-URL-03"))
    if en_cmb01 and has_urgency and has_risky_link:
        reasons.append(Reason(
            rule_id="R-CMB-01",
            group="CMB",
            title="Urgency Coupled with Risky Link",
            explanation="High-urgency psychological phrasing combined with an insecure or shortened URL.",
            evidence="Urgency keyword + HTTP/IP/Shortened link match",
            points=pts_cmb01
        ))

    # R-CMB-02: Brand Claim + Failed Authentication
    en_cmb02, pts_cmb02 = rule_meta("R-CMB-02", 10)
    has_brand_claim = any(r in matched_rule_ids for r in ("R-SND-04", "R-SND-08"))
    has_auth_fail = any(r in matched_rule_ids for r in ("R-SND-01", "R-SND-02", "R-SND-03"))
    if en_cmb02 and has_brand_claim and has_auth_fail:
        reasons.append(Reason(
            rule_id="R-CMB-02",
            group="CMB",
            title="Unauthenticated Brand Impersonation",
            explanation="Message claims to represent a recognized brand while failing sender cryptographic authentication (SPF/DKIM/DMARC).",
            evidence="Brand impersonation + SPF/DKIM/DMARC failure",
            points=pts_cmb02
        ))

    return reasons
