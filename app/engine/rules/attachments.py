from typing import List, Dict, Any, Tuple, Set
from ..models import ParsedEmail, Reason, AttachmentInfo

DEFAULT_DANGEROUS = {
    "exe", "bat", "cmd", "com", "scr", "pif", "vbs", "vbe", "js", "jse", 
    "wsf", "wsh", "ps1", "msi", "jar", "hta", "lnk", "reg", "dll", "cpl", "apk"
}
DEFAULT_MACRO = {"docm", "xlsm", "pptm", "dotm", "xlam"}
DEFAULT_ARCHIVE = {"zip", "rar", "7z", "iso", "img", "cab", "gz", "tar"}
DEFAULT_HTML = {"html", "htm", "shtml", "svg"}

def check(mail: ParsedEmail, cfg: Dict[str, Any]) -> List[Reason]:
    reasons: List[Reason] = []
    rules_cfg = cfg.get("rules", {})
    danger_cfg = cfg.get("dangerous_extensions", {})

    dangerous_exts = set(danger_cfg.get("dangerous", DEFAULT_DANGEROUS))
    macro_exts = set(danger_cfg.get("macro", DEFAULT_MACRO))
    archive_exts = set(danger_cfg.get("archive", DEFAULT_ARCHIVE))
    html_exts = set(danger_cfg.get("html", DEFAULT_HTML))

    def rule_meta(rule_id: str, default_pts: int) -> Tuple[bool, int]:
        r = rules_cfg.get(rule_id, {})
        return r.get("enabled", True), r.get("points", default_pts)

    en_r01, pts_r01 = rule_meta("R-ATT-01", 30)
    en_r02, pts_r02 = rule_meta("R-ATT-02", 25)
    en_r03, pts_r03 = rule_meta("R-ATT-03", 15)
    en_r04, pts_r04 = rule_meta("R-ATT-04", 8)
    en_r05, pts_r05 = rule_meta("R-ATT-05", 12)

    seen_danger = set()
    seen_double = set()
    seen_macro = set()
    seen_archive = set()
    seen_html = set()

    for att in mail.attachments:
        ext = att.ext.lower()
        chain = [e.lower() for e in att.ext_chain]

        # R-ATT-01: Dangerous Executable / Script File
        if en_r01 and ext in dangerous_exts and att.name not in seen_danger:
            seen_danger.add(att.name)
            reasons.append(Reason(
                rule_id="R-ATT-01",
                group="ATT",
                title="Dangerous Executable Attachment",
                explanation=f"Attachment '{att.name}' has executable or script extension '.{ext}', presenting extreme malware risk.",
                evidence=att.name,
                points=pts_r01
            ))

        # R-ATT-02: Double Extension Masking (e.g. invoice.pdf.exe)
        if en_r02 and len(chain) >= 2 and chain[-1] in dangerous_exts and att.name not in seen_double:
            seen_double.add(att.name)
            reasons.append(Reason(
                rule_id="R-ATT-02",
                group="ATT",
                title="Double Extension Deception",
                explanation=f"Attachment '{att.name}' uses deceptive multi-extension chaining (.{'.'.join(chain[-2:])}) to mask executable payload.",
                evidence=att.name,
                points=pts_r02
            ))

        # R-ATT-03: Macro-Enabled Document
        if en_r03 and ext in macro_exts and att.name not in seen_macro:
            seen_macro.add(att.name)
            reasons.append(Reason(
                rule_id="R-ATT-03",
                group="ATT",
                title="Macro-Enabled Office Document",
                explanation=f"Attachment '{att.name}' contains embedded VBA macros that can execute arbitrary code upon opening.",
                evidence=att.name,
                points=pts_r03
            ))

        # R-ATT-04: Archive / Disk Image
        if en_r04 and ext in archive_exts and att.name not in seen_archive:
            seen_archive.add(att.name)
            reasons.append(Reason(
                rule_id="R-ATT-04",
                group="ATT",
                title="Compressed Archive / Disk Image Attachment",
                explanation=f"Attachment '{att.name}' is an archive file commonly used to evade basic mail security filters.",
                evidence=att.name,
                points=pts_r04
            ))

        # R-ATT-05: HTML / SVG Phishing File
        if en_r05 and ext in html_exts and att.name not in seen_html:
            seen_html.add(att.name)
            reasons.append(Reason(
                rule_id="R-ATT-05",
                group="ATT",
                title="HTML / Scriptable Vector Attachment",
                explanation=f"Attachment '{att.name}' contains standalone HTML/SVG markup often used for offline phishing credential harvesting.",
                evidence=att.name,
                points=pts_r05
            ))

    return reasons
