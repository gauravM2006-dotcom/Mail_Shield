import re
from typing import List, Dict, Any, Set, Tuple
from ..models import ParsedEmail, Reason

def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def check(mail: ParsedEmail, cfg: Dict[str, Any]) -> List[Reason]:
    reasons: List[Reason] = []
    rules_cfg = cfg.get("rules", {})
    
    # Load lists
    brands_data = cfg.get("brands", []) # list of {"name":..., "domain":...}
    extra_brands = cfg.get("lists", {}).get("extra_brands", [])
    all_brands = list(brands_data)
    for b in extra_brands:
        if isinstance(b, dict):
            all_brands.append(b)
        elif isinstance(b, str) and ":" in b:
            name, dom = b.split(":", 1)
            all_brands.append({"name": name.strip(), "domain": dom.strip()})
            
    free_mail_domains = set(cfg.get("free_mail_domains", []))
    disposable_domains = set(cfg.get("disposable_domains", []))
    suspicious_tlds = set(cfg.get("suspicious_tlds", []))

    # Helper to check if rule is enabled and get points
    def rule_meta(rule_id: str, default_pts: int) -> Tuple[bool, int]:
        r = rules_cfg.get(rule_id, {})
        return r.get("enabled", True), r.get("points", default_pts)

    # R-SND-01: SPF failed
    en, pts = rule_meta("R-SND-01", 10)
    if en:
        spf = mail.auth.get("spf", "none").lower()
        if spf == "fail":
            reasons.append(Reason(
                rule_id="R-SND-01",
                group="SND",
                title="SPF Authentication Failed",
                explanation="The sending server is not authorized to send mail for this domain (SPF fail).",
                evidence=f"spf={spf}",
                points=pts
            ))
        elif spf == "softfail":
            reasons.append(Reason(
                rule_id="R-SND-01",
                group="SND",
                title="SPF Softfail",
                explanation="The sending server failed strict SPF verification (SPF softfail).",
                evidence=f"spf={spf}",
                points=max(1, pts // 2)
            ))

    # R-SND-02: DKIM failed
    en, pts = rule_meta("R-SND-02", 10)
    if en:
        dkim = mail.auth.get("dkim", "none").lower()
        if dkim == "fail":
            reasons.append(Reason(
                rule_id="R-SND-02",
                group="SND",
                title="DKIM Signature Verification Failed",
                explanation="Cryptographic signature verification failed (DKIM fail), indicating possible message tampering.",
                evidence=f"dkim={dkim}",
                points=pts
            ))

    # R-SND-03: DMARC failed
    en, pts = rule_meta("R-SND-03", 15)
    if en:
        dmarc = mail.auth.get("dmarc", "none").lower()
        if dmarc == "fail":
            reasons.append(Reason(
                rule_id="R-SND-03",
                group="SND",
                title="DMARC Policy Failed",
                explanation="The sender domain failed DMARC alignment and authentication policy.",
                evidence=f"dmarc={dmarc}",
                points=pts
            ))

    # Find matching brand in display name or subject
    sender_disp = mail.from_name.lower()
    sender_domain = mail.from_domain.lower()
    sender_reg = mail.from_registrable.lower()

    matched_brand_for_disp = None
    for b in all_brands:
        b_name = b.get("name", "").lower()
        b_domain = b.get("domain", "").lower()
        if b_name and (re.search(rf'\b{re.escape(b_name)}\b', sender_disp) or b_name in sender_disp):
            matched_brand_for_disp = (b_name, b_domain)
            break

    # R-SND-04: Display-name mismatch
    en, pts = rule_meta("R-SND-04", 15)
    if en and matched_brand_for_disp:
        b_name, b_domain = matched_brand_for_disp
        # If the sender registrable domain is NOT the brand's domain
        if sender_reg and not (sender_reg == b_domain or sender_domain.endswith("." + b_domain)):
            reasons.append(Reason(
                rule_id="R-SND-04",
                group="SND",
                title="Display Name Brand Mismatch",
                explanation=f"Display name claims to be '{mail.from_name}' but the email originates from external domain '{sender_domain}'.",
                evidence=f"Display: '{mail.from_name}' vs Sender: <{mail.from_address}>",
                points=pts
            ))

    # R-SND-05: Look-alike domain (Typosquatting)
    en, pts = rule_meta("R-SND-05", 20)
    if en and sender_domain:
        # Check domain parts for edit distance 1 with brand names (len >= 5)
        # e.g., "paypa1-secure.top" -> labels "paypa1", "secure" -> "paypa1" vs "paypal" dist = 1
        labels = re.split(r'[\.\-]', sender_domain)
        found_lookalike = False
        for lbl in labels:
            if len(lbl) < 4:
                continue
            for b in all_brands:
                b_name = b.get("name", "").lower()
                b_dom = b.get("domain", "").lower()
                b_label = b_dom.split(".")[0] if "." in b_dom else b_name
                if len(b_label) >= 4 and lbl != b_label and sender_reg != b_dom:
                    dist = levenshtein_distance(lbl, b_label)
                    # Edit distance 1 or subtle substitutions (1 for l, 0 for o)
                    if dist == 1 or (len(lbl) == len(b_label) and dist <= 2 and any(c.isdigit() for c in lbl)):
                        reasons.append(Reason(
                            rule_id="R-SND-05",
                            group="SND",
                            title="Look-alike / Impersonated Domain",
                            explanation=f"Sender domain '{sender_domain}' uses typosquatted variation of brand '{b_name}' ({b_dom}).",
                            evidence=f"'{lbl}' closely mimics brand domain '{b_dom}'",
                            points=pts
                        ))
                        found_lookalike = True
                        break
            if found_lookalike:
                break

    # R-SND-06: Reply-To differs
    en, pts = rule_meta("R-SND-06", 8)
    if en and mail.reply_to_address:
        if mail.reply_to_registrable and mail.from_registrable:
            if mail.reply_to_registrable != mail.from_registrable:
                reasons.append(Reason(
                    rule_id="R-SND-06",
                    group="SND",
                    title="Reply-To Domain Mismatch",
                    explanation="Responses will be redirected to a different organization domain than the sender.",
                    evidence=f"From: {mail.from_address} -> Reply-To: {mail.reply_to_address}",
                    points=pts
                ))

    # R-SND-07: Disposable domain
    en, pts = rule_meta("R-SND-07", 12)
    if en and sender_domain in disposable_domains:
        reasons.append(Reason(
            rule_id="R-SND-07",
            group="SND",
            title="Disposable Email Provider",
            explanation="The email was sent from a temporary / throwaway email service commonly used by spammers.",
            evidence=sender_domain,
            points=pts
        ))

    # R-SND-08: Brand via free mail
    en, pts = rule_meta("R-SND-08", 10)
    if en and matched_brand_for_disp and sender_domain in free_mail_domains:
        b_name, _ = matched_brand_for_disp
        reasons.append(Reason(
            rule_id="R-SND-08",
            group="SND",
            title="Brand Impersonation via Free Mail",
            explanation=f"Sender claims to represent brand '{b_name}' but sent message from a free public mailbox ({sender_domain}).",
            evidence=f"Brand: {b_name} from {mail.from_address}",
            points=pts
        ))

    # R-SND-09: Invalid sender domain syntax
    en, pts = rule_meta("R-SND-09", 15)
    if en:
        domain_valid = bool(re.match(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$', sender_domain)) if sender_domain else False
        if not domain_valid and sender_domain:
            reasons.append(Reason(
                rule_id="R-SND-09",
                group="SND",
                title="Malformed Sender Domain",
                explanation=f"Sender domain '{sender_domain}' fails standard RFC host syntax validation.",
                evidence=sender_domain,
                points=pts
            ))

    # R-SND-10: Suspicious TLD
    en, pts = rule_meta("R-SND-10", 6)
    if en and mail.from_tld and mail.from_tld in suspicious_tlds:
        reasons.append(Reason(
            rule_id="R-SND-10",
            group="SND",
            title="High-Abuse Top-Level Domain (TLD)",
            explanation=f"Sender domain uses top-level domain '.{mail.from_tld}' with a statistically high volume of abusive email.",
            evidence=f".{mail.from_tld}",
            points=pts
        ))

    return reasons
