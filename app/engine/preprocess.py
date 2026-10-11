import re
import unicodedata
import ipaddress
from urllib.parse import urlparse, unquote
import email
from email import policy
from email.parser import BytesParser
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
from .models import ParsedEmail, ExtractedURL, AttachmentInfo

try:
    import tldextract
    _extract_tld = tldextract.TLDExtract(suffix_list_urls=None)
except ImportError:
    _extract_tld = None

def normalize_text(text: str) -> str:
    """Normalize text with Unicode NFKC, remove zero-width chars and collapse whitespace."""
    if not text:
        return ""
    # Unicode NFKC
    norm = unicodedata.normalize("NFKC", text)
    # Remove zero-width characters & soft hyphens
    norm = re.sub(r'[\u200B-\u200D\uFEFF\u00AD]', '', norm)
    # Collapse multiple whitespaces
    norm = re.sub(r'\s+', ' ', norm)
    return norm.strip()

def split_domain(domain_or_host: str) -> Tuple[str, str, str]:
    """Return (subdomain, registrable_domain, tld)."""
    clean_host = domain_or_host.lower().strip("[]").split(":")[0]
    if _extract_tld:
        ext = _extract_tld(clean_host)
        registrable = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
        return ext.subdomain, registrable, ext.suffix
    parts = clean_host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[:-2]), ".".join(parts[-2:]), parts[-1]
    return "", clean_host, ""

def is_ip_host(host: str) -> bool:
    """Check if host is an IPv4 or IPv6 address."""
    clean = host.strip("[]").split(":")[0]
    try:
        ipaddress.ip_address(clean)
        return True
    except ValueError:
        # Check decimal / hex representation
        if clean.isdigit():
            return True
        return False

def is_punycode(host: str) -> bool:
    """Check if host contains punycode prefix xn--."""
    return "xn--" in host.lower()

def html_to_text(html_content: str) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Extract visible text and links from HTML content.
    Strips script, style, and hidden elements (display:none, visibility:hidden).
    Returns (cleaned_text, list_of_(href, link_text)).
    """
    if not html_content:
        return "", []
    
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Remove script, style, head, noscript
    for el in soup(["script", "style", "head", "noscript", "template"]):
        el.decompose()
        
    # Remove hidden elements (e.g. style="display:none")
    for el in soup.find_all(style=True):
        style = el["style"].lower().replace(" ", "")
        if "display:none" in style or "visibility:hidden" in style or "font-size:0" in style or "opacity:0" in style:
            el.decompose()

    extracted_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        link_text = a.get_text(separator=" ", strip=True)
        if href:
            extracted_links.append((href, link_text))

    text = soup.get_text(separator=" ", strip=True)
    return text, extracted_links

def extract_urls(raw_text: str, html_links: Optional[List[Tuple[str, str]]] = None) -> List[ExtractedURL]:
    """Extract all URLs from text and HTML anchor tags, standardizing properties."""
    seen_hrefs = set()
    results = []

    def process_url(href: str, anchor_text: str = ""):
        if not href or href in seen_hrefs or href.startswith("mailto:") or href.startswith("javascript:") or href.startswith("tel:"):
            return
        seen_hrefs.add(href)
        
        parsed = urlparse(href if "://" in href else f"http://{href}")
        scheme = parsed.scheme.lower()
        host = parsed.netloc.lower()
        if "@" in host:
            has_at = True
            host_clean = host.split("@")[-1]
        else:
            has_at = False
            host_clean = host

        port = parsed.port
        subdomain, registrable, tld = split_domain(host_clean)
        
        results.append(ExtractedURL(
            href=href,
            text=anchor_text,
            scheme=scheme,
            host=host_clean,
            registrable=registrable,
            subdomain=subdomain,
            tld=tld,
            port=port,
            path=parsed.path,
            has_at=has_at,
            is_ip=is_ip_host(host_clean),
            is_punycode=is_punycode(host_clean),
            length=len(href)
        ))

    if html_links:
        for href, text in html_links:
            process_url(href, text)

    # Regex search for plain text URLs
    url_pattern = r'https?://[^\s<>"\')]+'
    for match in re.finditer(url_pattern, raw_text, re.IGNORECASE):
        process_url(match.group(0), "")

    return results

def parse_auth_results(header_val: str) -> Dict[str, str]:
    """Parse SPF, DKIM, DMARC statuses from Authentication-Results or ARC headers."""
    auth = {"spf": "none", "dkim": "none", "dmarc": "none"}
    if not header_val:
        return auth
    
    header_lower = header_val.lower()
    
    # SPF
    spf_match = re.search(r'spf=(\w+)', header_lower)
    if spf_match:
        auth["spf"] = spf_match.group(1)
        
    # DKIM
    dkim_match = re.search(r'dkim=(\w+)', header_lower)
    if dkim_match:
        auth["dkim"] = dkim_match.group(1)
        
    # DMARC
    dmarc_match = re.search(r'dmarc=(\w+)', header_lower)
    if dmarc_match:
        auth["dmarc"] = dmarc_match.group(1)

    return auth

def to_parsed_email(data: Dict[str, Any]) -> ParsedEmail:
    """Convert normalized dictionary (from db or manual input) to ParsedEmail model."""
    from_dict = data.get("from", {})
    from_name = from_dict.get("name", "") if isinstance(from_dict, dict) else ""
    from_address = from_dict.get("address", "") if isinstance(from_dict, dict) else (str(from_dict) if isinstance(from_dict, str) else "")
    
    from_domain = ""
    if "@" in from_address:
        from_domain = from_address.split("@")[-1].lower()
    elif isinstance(from_dict, dict) and from_dict.get("domain"):
        from_domain = from_dict.get("domain", "").lower()
        
    from_sub, from_reg, from_tld = split_domain(from_domain)

    reply_to = data.get("reply_to", {})
    reply_to_addr = reply_to.get("address", "") if isinstance(reply_to, dict) else (str(reply_to) if isinstance(reply_to, str) else "")
    reply_to_dom = reply_to_addr.split("@")[-1].lower() if "@" in reply_to_addr else ""
    _, reply_to_reg, _ = split_domain(reply_to_dom)

    subject_raw = data.get("subject", "") or ""
    body_raw = data.get("body_text", "") or data.get("body", "") or ""

    subject_norm = normalize_text(subject_raw).lower()
    body_norm = normalize_text(body_raw).lower()

    # URLs
    urls_list: List[ExtractedURL] = []
    raw_urls = data.get("urls", [])
    if raw_urls and isinstance(raw_urls, list):
        for u in raw_urls:
            if isinstance(u, dict):
                href = u.get("href", "")
                text = u.get("text", "")
                urls_list.extend(extract_urls(href, [(href, text)]))
            elif isinstance(u, str):
                urls_list.extend(extract_urls(u))
    else:
        urls_list = extract_urls(body_raw)

    # Attachments
    attachments: List[AttachmentInfo] = []
    for att in data.get("attachments", []):
        if isinstance(att, dict):
            name = att.get("name", "") or att.get("filename", "")
            ext = att.get("ext", "")
            size = att.get("size", 0) or att.get("size_bytes", 0)
            mime = att.get("mime", "") or att.get("content_type", "")
        else:
            name = str(att)
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            size = 0
            mime = ""
            
        parts = name.split(".")
        ext_chain = [p.lower() for p in parts[1:]] if len(parts) > 1 else []
        if not ext and ext_chain:
            ext = ext_chain[-1]
            
        attachments.append(AttachmentInfo(
            name=name,
            ext=ext,
            ext_chain=ext_chain,
            size=size,
            mime=mime
        ))

    auth = data.get("auth_results", {}) or data.get("auth", {})
    auth_normalized = {
        "spf": auth.get("spf", "none").lower(),
        "dkim": auth.get("dkim", "none").lower(),
        "dmarc": auth.get("dmarc", "none").lower()
    }

    return ParsedEmail(
        subject_raw=subject_raw,
        subject=subject_norm,
        body_raw=body_raw,
        body=body_norm,
        from_name=from_name,
        from_address=from_address,
        from_domain=from_domain,
        from_subdomain=from_sub,
        from_registrable=from_reg,
        from_tld=from_tld,
        to=data.get("to", []),
        reply_to_address=reply_to_addr,
        reply_to_domain=reply_to_dom,
        reply_to_registrable=reply_to_reg,
        urls=urls_list,
        attachments=attachments,
        auth=auth_normalized,
        text_for_keywords=f"{subject_norm} {body_norm}",
        message_id=data.get("provider_msg_id", data.get("message_id", "")),
        received_at=data.get("received_at")
    )

def parse_raw_mail(raw_bytes: bytes) -> ParsedEmail:
    """Parse an RFC 822 / MIME raw email byte string into ParsedEmail."""
    msg = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    
    subject_raw = msg.get("Subject", "")
    from_raw = msg.get("From", "")
    to_raw = msg.get("To", "")
    reply_to_raw = msg.get("Reply-To", "")
    auth_results_raw = msg.get("Authentication-Results", "") or msg.get("ARC-Authentication-Results", "")
    
    from_name, from_address = email.utils.parseaddr(from_raw)
    from_domain = from_address.split("@")[-1].lower() if "@" in from_address else ""
    from_sub, from_reg, from_tld = split_domain(from_domain)
    
    reply_to_name, reply_to_addr = email.utils.parseaddr(reply_to_raw)
    reply_to_dom = reply_to_addr.split("@")[-1].lower() if "@" in reply_to_addr else ""
    _, reply_to_reg, _ = split_domain(reply_to_dom)
    
    body_text_parts = []
    html_parts = []
    attachments = []
    
    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        filename = part.get_filename()
        content_type = part.get_content_type()
        
        if filename or "attachment" in content_disposition:
            fname = filename or "unnamed_attachment"
            parts = fname.split(".")
            ext_chain = [p.lower() for p in parts[1:]] if len(parts) > 1 else []
            ext = ext_chain[-1] if ext_chain else ""
            payload = part.get_payload(decode=True)
            size = len(payload) if payload else 0
            attachments.append(AttachmentInfo(
                name=fname,
                ext=ext,
                ext_chain=ext_chain,
                size=size,
                mime=content_type
            ))
        elif content_type == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                body_text_parts.append(payload.decode(charset, errors="replace"))
        elif content_type == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                html_parts.append(payload.decode(charset, errors="replace"))

    html_links = []
    if html_parts:
        combined_html = "\n".join(html_parts)
        extracted_text, html_links = html_to_text(combined_html)
        if not body_text_parts:
            body_text_parts.append(extracted_text)

    body_raw = "\n".join(body_text_parts)
    subject_norm = normalize_text(subject_raw).lower()
    body_norm = normalize_text(body_raw).lower()
    urls = extract_urls(body_raw, html_links)
    auth = parse_auth_results(auth_results_raw)

    return ParsedEmail(
        subject_raw=subject_raw,
        subject=subject_norm,
        body_raw=body_raw,
        body=body_norm,
        from_name=from_name,
        from_address=from_address,
        from_domain=from_domain,
        from_subdomain=from_sub,
        from_registrable=from_reg,
        from_tld=from_tld,
        to=[{"name": "", "address": to_raw}],
        reply_to_address=reply_to_addr,
        reply_to_domain=reply_to_dom,
        reply_to_registrable=reply_to_reg,
        urls=urls,
        attachments=attachments,
        auth=auth,
        text_for_keywords=f"{subject_norm} {body_norm}",
        message_id=msg.get("Message-ID", "")
    )
