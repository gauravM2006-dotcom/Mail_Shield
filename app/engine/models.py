from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class ExtractedURL:
    href: str
    text: str = ""
    scheme: str = ""
    host: str = ""
    registrable: str = ""
    subdomain: str = ""
    tld: str = ""
    port: Optional[int] = None
    path: str = ""
    has_at: bool = False
    is_ip: bool = False
    is_punycode: bool = False
    length: int = 0

@dataclass
class AttachmentInfo:
    name: str
    ext: str = ""
    ext_chain: List[str] = field(default_factory=list)
    size: int = 0
    mime: str = ""

@dataclass
class ParsedEmail:
    subject_raw: str = ""
    subject: str = ""
    body_raw: str = ""
    body: str = ""
    from_name: str = ""
    from_address: str = ""
    from_domain: str = ""
    from_subdomain: str = ""
    from_registrable: str = ""
    from_tld: str = ""
    to: List[Dict[str, str]] = field(default_factory=list)
    reply_to_address: str = ""
    reply_to_domain: str = ""
    reply_to_registrable: str = ""
    urls: List[ExtractedURL] = field(default_factory=list)
    attachments: List[AttachmentInfo] = field(default_factory=list)
    auth: Dict[str, str] = field(default_factory=lambda: {"spf": "none", "dkim": "none", "dmarc": "none"})
    text_for_keywords: str = ""
    message_id: str = ""
    received_at: Optional[str] = None

@dataclass
class Reason:
    rule_id: str
    group: str
    title: str
    explanation: str
    evidence: str
    points: int

@dataclass
class ScanResult:
    score: int
    label: str  # "safe" | "suspicious" | "spam"
    reasons: List[Reason]
    group_scores: Dict[str, int]
    rules_version: int = 1
    thresholds: Dict[str, int] = field(default_factory=lambda: {"suspicious": 30, "spam": 60})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "label": self.label,
            "reasons": [
                {
                    "rule_id": r.rule_id,
                    "group": r.group,
                    "title": r.title,
                    "explanation": r.explanation,
                    "evidence": r.evidence,
                    "points": r.points
                }
                for r in self.reasons
            ],
            "group_scores": self.group_scores,
            "rules_version": self.rules_version,
            "thresholds": self.thresholds
        }
