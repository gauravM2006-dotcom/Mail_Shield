import re
import math
from typing import List, Dict, Any, Set, Tuple
from ..models import ParsedEmail, Reason

OBFUSCATION_MAP = {
    '0': 'o',
    '1': 'i',
    '3': 'e',
    '4': 'a',
    '@': 'a',
    '$': 's',
    '5': 's',
    '7': 't',
    '+': 't',
    '!': 'i'
}

def deobfuscate(text: str) -> str:
    """Replace common leetspeak characters and remove dots/dashes between letters."""
    chars = [OBFUSCATION_MAP.get(c.lower(), c) for c in text]
    deob = "".join(chars)
    deob = re.sub(r'(?<=\b\w)[.\-_](?=\w)', '', deob)
    return deob.lower()

def check(mail: ParsedEmail, cfg: Dict[str, Any]) -> List[Reason]:
    reasons: List[Reason] = []
    categories = cfg.get("keyword_categories", [])
    rules_cfg = cfg.get("rules", {})

    subject_lower = mail.subject
    body_lower = mail.body
    deob_subject = deobfuscate(mail.subject_raw)
    deob_body = deobfuscate(mail.body_raw)

    for cat in categories:
        if not cat.get("enabled", True):
            continue

        cat_key = cat.get("key", "")
        rule_id = cat.get("rule_id", f"R-KW-{cat_key}")
        base_weight = cat.get("weight", 8)
        
        rule_override = rules_cfg.get(rule_id, {})
        if not rule_override.get("enabled", True):
            continue
        weight = rule_override.get("points", base_weight)

        keywords: List[str] = sorted(cat.get("keywords", []), key=lambda x: len(x), reverse=True)
        
        subject_spans: List[Tuple[int, int]] = []
        body_spans: List[Tuple[int, int]] = []
        
        matched_in_subject: List[str] = []
        matched_in_body: List[str] = []
        obfuscated_matches: Set[str] = set()

        def overlaps(spans: List[Tuple[int, int]], start: int, end: int) -> bool:
            return any(max(start, s) < min(end, e) for s, e in spans)

        for kw in keywords:
            kw_clean = kw.strip().lower()
            if not kw_clean:
                continue

            escaped_kw = re.escape(kw_clean)
            pattern = re.compile(rf'\b{escaped_kw}\b', re.IGNORECASE)

            # Check subject
            m_subj = pattern.search(subject_lower)
            if m_subj and not overlaps(subject_spans, m_subj.start(), m_subj.end()):
                subject_spans.append((m_subj.start(), m_subj.end()))
                matched_in_subject.append(kw_clean)
            else:
                # Check body
                m_body = pattern.search(body_lower)
                if m_body and not overlaps(body_spans, m_body.start(), m_body.end()):
                    body_spans.append((m_body.start(), m_body.end()))
                    matched_in_body.append(kw_clean)
                else:
                    # Check obfuscated
                    if pattern.search(deob_subject) or pattern.search(deob_body):
                        obfuscated_matches.add(kw_clean)

        for kw in matched_in_subject:
            pts = math.ceil(weight * 1.5)
            reasons.append(Reason(
                rule_id=rule_id,
                group="KW",
                title=cat.get("label", "Spam Keyword"),
                explanation=f"Found high-risk phrase '{kw}' in the subject line (1.5x multiplier applied).",
                evidence=kw,
                points=pts
            ))

        for kw in matched_in_body:
            reasons.append(Reason(
                rule_id=rule_id,
                group="KW",
                title=cat.get("label", "Spam Keyword"),
                explanation=f"Found trigger keyword/phrase '{kw}' in email body.",
                evidence=kw,
                points=weight
            ))

        obfus_rule_cfg = rules_cfg.get("R-KW-08", {})
        if obfus_rule_cfg.get("enabled", True):
            obfus_weight = obfus_rule_cfg.get("points", 6)
            for kw in obfuscated_matches:
                reasons.append(Reason(
                    rule_id="R-KW-08",
                    group="KW",
                    title="Obfuscated Keyword",
                    explanation=f"Detected obfuscated/leetspeak variation of restricted keyword '{kw}'.",
                    evidence=kw,
                    points=obfus_weight
                ))

    return reasons
