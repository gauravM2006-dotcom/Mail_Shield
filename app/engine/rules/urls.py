import re
from typing import List, Dict, Any, Tuple
from ..models import ParsedEmail, Reason, ExtractedURL

def check(mail: ParsedEmail, cfg: Dict[str, Any]) -> List[Reason]:
    reasons: List[Reason] = []
    rules_cfg = cfg.get("rules", {})
    
    shorteners = set(cfg.get("shorteners", []))
    suspicious_tlds = set(cfg.get("suspicious_tlds", []))
    brands = cfg.get("brands", [])

    def rule_meta(rule_id: str, default_pts: int) -> Tuple[bool, int]:
        r = rules_cfg.get(rule_id, {})
        return r.get("enabled", True), r.get("points", default_pts)

    http_count = 0
    en_r01, pts_r01 = rule_meta("R-URL-01", 8)
    en_r02, pts_r02 = rule_meta("R-URL-02", 20)
    en_r03, pts_r03 = rule_meta("R-URL-03", 12)
    en_r04, pts_r04 = rule_meta("R-URL-04", 10)
    en_r05, pts_r05 = rule_meta("R-URL-05", 15)
    en_r06, pts_r06 = rule_meta("R-URL-06", 15)
    en_r07, pts_r07 = rule_meta("R-URL-07", 18)
    en_r08, pts_r08 = rule_meta("R-URL-08", 12)
    en_r09, pts_r09 = rule_meta("R-URL-09", 4)
    en_r10, pts_r10 = rule_meta("R-URL-10", 5)
    en_r11, pts_r11 = rule_meta("R-URL-11", 10)

    seen_ip_hosts = set()
    seen_shorteners = set()
    seen_suspicious_tlds = set()
    seen_punycodes = set()
    seen_at_tricks = set()
    seen_misleading = set()
    seen_brand_subdomains = set()
    seen_long_urls = set()
    seen_unusual_ports = set()
    seen_invalid_domains = set()

    for url in mail.urls:
        # R-URL-01: Insecure HTTP Protocol
        if en_r01 and url.scheme == "http":
            http_count += 1
            if http_count <= 2:
                reasons.append(Reason(
                    rule_id="R-URL-01",
                    group="URL",
                    title="Insecure HTTP Link",
                    explanation="Link uses unencrypted HTTP protocol rather than secure HTTPS.",
                    evidence=url.href,
                    points=pts_r01
                ))

        # R-URL-02: IP Address as Host
        if en_r02 and url.is_ip and url.host not in seen_ip_hosts:
            seen_ip_hosts.add(url.host)
            reasons.append(Reason(
                rule_id="R-URL-02",
                group="URL",
                title="Direct IP Address Host",
                explanation="Destination link points directly to a raw IP address literal rather than a verified registered domain.",
                evidence=url.href,
                points=pts_r02
            ))

        # R-URL-03: URL Shortener
        if en_r03 and (url.registrable in shorteners or url.host in shorteners) and url.host not in seen_shorteners:
            seen_shorteners.add(url.host)
            reasons.append(Reason(
                rule_id="R-URL-03",
                group="URL",
                title="URL Shortener Detected",
                explanation="Link hides its true destination behind a public URL shortening service.",
                evidence=url.href,
                points=pts_r03
            ))

        # R-URL-04: Suspicious TLD
        if en_r04 and url.tld in suspicious_tlds and url.tld not in seen_suspicious_tlds:
            seen_suspicious_tlds.add(url.tld)
            reasons.append(Reason(
                rule_id="R-URL-04",
                group="URL",
                title="Suspicious Top-Level Domain (TLD)",
                explanation=f"Link points to a domain ending in high-abuse TLD '.{url.tld}'.",
                evidence=url.href,
                points=pts_r04
            ))

        # R-URL-05: Punycode / IDN
        if en_r05 and url.is_punycode and url.host not in seen_punycodes:
            seen_punycodes.add(url.host)
            reasons.append(Reason(
                rule_id="R-URL-05",
                group="URL",
                title="Punycode / Homograph Link",
                explanation="Host contains Punycode ('xn--') indicating potential internationalized homograph attack.",
                evidence=url.host,
                points=pts_r05
            ))

        # R-URL-06: '@' credential trick
        if en_r06 and url.has_at and url.href not in seen_at_tricks:
            seen_at_tricks.add(url.href)
            reasons.append(Reason(
                rule_id="R-URL-06",
                group="URL",
                title="Embedded '@' Symbol in URL",
                explanation="URL contains '@' syntax which misleads the user about the actual target host.",
                evidence=url.href,
                points=pts_r06
            ))

        # R-URL-07: Misleading Link Text (Anchor Text Mismatch)
        if en_r07 and url.text:
            text_clean = url.text.strip().lower()
            text_dom_match = re.search(r'(?:https?://)?(?:www\.)?([a-z0-9\-\.]+\.[a-z]{2,})', text_clean)
            if text_dom_match:
                claimed_dom = text_dom_match.group(1).lower()
                real_dom = url.registrable or url.host
                if claimed_dom != real_dom and not claimed_dom.endswith("." + real_dom) and not real_dom.endswith("." + claimed_dom):
                    key = f"{claimed_dom}->{real_dom}"
                    if key not in seen_misleading:
                        seen_misleading.add(key)
                        reasons.append(Reason(
                            rule_id="R-URL-07",
                            group="URL",
                            title="Misleading Link Text",
                            explanation=f"Visible text shows '{url.text}' but actually directs to '{url.href}'.",
                            evidence=f"Text: '{url.text}' -> Href: '{url.href}'",
                            points=pts_r07
                        ))

        # R-URL-08: Brand in Subdomain/Path or Deep Subdomains (>3 levels)
        if en_r08 and url.host not in seen_brand_subdomains:
            # Check brand in subdomain or path when registrable domain is not that brand
            for b in brands:
                b_name = b.get("name", "").lower()
                b_dom = b.get("domain", "").lower()
                if len(b_name) >= 3:
                    pattern = re.compile(rf'\b{re.escape(b_name)}\b', re.IGNORECASE)
                    if pattern.search(url.subdomain) or pattern.search(url.path):
                        if url.registrable != b_dom and not url.host.endswith("." + b_dom):
                            seen_brand_subdomains.add(url.host)
                            reasons.append(Reason(
                                rule_id="R-URL-08",
                                group="URL",
                                title="Brand Impersonation in Link Structure",
                                explanation=f"Brand '{b_name}' is placed in subdomain/path of third-party domain '{url.registrable}'.",
                                evidence=url.href,
                                points=pts_r08
                            ))
                            break

            # Deep subdomains (>3 labels in subdomain)
            sub_labels = [p for p in url.subdomain.split(".") if p]
            if len(sub_labels) >= 3 and url.host not in seen_brand_subdomains:
                seen_brand_subdomains.add(url.host)
                reasons.append(Reason(
                    rule_id="R-URL-08",
                    group="URL",
                    title="Excessive Subdomain Depth",
                    explanation=f"Host uses complex multi-level subdomains ({len(sub_labels)} levels) often seen in dynamic phishing links.",
                    evidence=url.host,
                    points=pts_r08
                ))

        # R-URL-09: Very long URL (>200 chars)
        if en_r09 and url.length > 200 and url.href not in seen_long_urls:
            seen_long_urls.add(url.href)
            reasons.append(Reason(
                rule_id="R-URL-09",
                group="URL",
                title="Excessively Long URL",
                explanation=f"Link length ({url.length} characters) exceeds 200 characters, frequently used for obfuscation.",
                evidence=f"Length: {url.length} chars",
                points=pts_r09
            ))

        # R-URL-10: Unusual Port
        if en_r10 and url.port and url.port not in (80, 443) and url.href not in seen_unusual_ports:
            seen_unusual_ports.add(url.href)
            reasons.append(Reason(
                rule_id="R-URL-10",
                group="URL",
                title="Non-Standard Port in Link",
                explanation=f"Link specifies non-standard web port {url.port}.",
                evidence=url.href,
                points=pts_r10
            ))

        # R-URL-11: Invalid Link Host Syntax
        if en_r11 and url.host and not url.is_ip and url.host not in seen_invalid_domains:
            valid_syntax = bool(re.match(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$', url.host))
            if not valid_syntax and "localhost" not in url.host:
                seen_invalid_domains.add(url.host)
                reasons.append(Reason(
                    rule_id="R-URL-11",
                    group="URL",
                    title="Malformed Link Domain",
                    explanation=f"Host '{url.host}' fails standard domain name validation.",
                    evidence=url.host,
                    points=pts_r11
                ))

    return reasons
