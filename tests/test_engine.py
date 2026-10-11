import pytest
from app.engine import to_parsed_email, scan_email, ParsedEmail, ExtractedURL, AttachmentInfo
from app.engine.rules.custom import is_safe_regex
from app.rules.defaults import get_default_rule_config

@pytest.fixture
def default_config():
    return get_default_rule_config()

def test_case_1_plain_personal_mail(default_config):
    """Test Case 1: Plain personal mail, no links, SPF pass -> score 0, Safe, no reasons."""
    mail_data = {
        "from": {"name": "Alice Smith", "address": "alice@company.com", "domain": "company.com"},
        "subject": "Lunch meeting tomorrow at noon",
        "body_text": "Hi Bob, are we still meeting for lunch tomorrow at the cafeteria?",
        "urls": [],
        "attachments": [],
        "auth_results": {"spf": "pass", "dkim": "pass", "dmarc": "pass"}
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, default_config)
    assert res.score == 0
    assert res.label == "safe"
    assert len(res.reasons) == 0

def test_case_2_example_1_obvious_phishing(default_config):
    """Test Case 2: Example 1 obvious phishing (Section 12.7)."""
    mail_data = {
        "from": {"name": "PayPal Support", "address": "service@paypa1-secure.top", "domain": "paypa1-secure.top"},
        "reply_to": {"name": "", "address": "collect@free-mail.example"},
        "subject": "URGENT!!! Verify your account NOW",
        "body_text": "Dear customer, your account has been limited. Please click http://203.0.113.9/login to verify your identity immediately.",
        "urls": [
            {"href": "http://203.0.113.9/login", "text": "www.paypal.com"}
        ],
        "attachments": [
            {"name": "invoice.pdf.exe", "ext": "exe", "size": 48211}
        ],
        "auth_results": {"spf": "fail", "dkim": "none", "dmarc": "fail"}
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, default_config)
    assert res.score == 100
    assert res.label == "spam"
    
    rule_ids = {r.rule_id for r in res.reasons}
    assert "R-SND-05" in rule_ids or "R-SND-04" in rule_ids
    assert "R-URL-02" in rule_ids
    assert "R-ATT-02" in rule_ids
    assert "R-ATT-01" in rule_ids

def test_case_3_example_2_borderline_prize(default_config):
    """Test Case 3: Example 2 borderline (prize keywords + shortener)."""
    mail_data = {
        "from": {"name": "Prize Desk", "address": "desk@promo-win.example", "domain": "promo-win.example"},
        "subject": "You are a winner - claim your reward",
        "body_text": "Congratulations! Claim your reward at https://bit.ly/x1 today.",
        "urls": [
            {"href": "https://bit.ly/x1", "text": "https://bit.ly/x1"}
        ],
        "attachments": [],
        "auth_results": {"spf": "pass", "dkim": "none", "dmarc": "none"}
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, default_config)
    assert res.label == "suspicious"
    assert 30 <= res.score < 60

def test_case_4_example_3_normal_newsletter(default_config):
    """Test Case 4: Normal newsletter with discount and unsubscribe."""
    mail_data = {
        "from": {"name": "Tech Weekly", "address": "newsletter@techweekly.com", "domain": "techweekly.com"},
        "subject": "Big discount this weekend",
        "body_text": "Check out our weekend special offer. You can unsubscribe at any time.",
        "urls": [
            {"href": "https://techweekly.com/specials", "text": "View Specials"},
            {"href": "https://techweekly.com/unsubscribe", "text": "Unsubscribe"}
        ],
        "attachments": [],
        "auth_results": {"spf": "pass", "dkim": "pass", "dmarc": "pass"}
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, default_config)
    assert res.score < 30
    assert res.label == "safe"

def test_case_5_shouting_and_punctuation(default_config):
    """Test Case 5: Subject 'FREE!!! WIN NOW!!!' (all caps and punctuation)."""
    mail_data = {
        "from": {"name": "Info", "address": "info@example.com", "domain": "example.com"},
        "subject": "FREE!!! WIN NOW!!!",
        "body_text": "Claim it here.",
        "auth_results": {"spf": "pass", "dkim": "pass", "dmarc": "pass"}
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, default_config)
    rule_ids = {r.rule_id for r in res.reasons}
    assert "R-CAP-01" in rule_ids
    assert "R-PUN-01" in rule_ids

def test_case_6_misleading_link_text(default_config):
    """Test Case 6: Anchor text 'www.bank.com', href 'https://evil.example/x'."""
    mail_data = {
        "from": {"name": "Service", "address": "service@example.com", "domain": "example.com"},
        "subject": "Account update",
        "body_text": "Visit www.chase.com to update your preferences.",
        "urls": [
            {"href": "https://evil.example/x", "text": "www.chase.com"}
        ]
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, default_config)
    rule_ids = {r.rule_id for r in res.reasons}
    assert "R-URL-07" in rule_ids

def test_case_7_double_extension_attachment(default_config):
    """Test Case 7: Attachment report.pdf.exe triggers dangerous and double extension."""
    mail_data = {
        "from": {"name": "HR Dept", "address": "hr@partner.com", "domain": "partner.com"},
        "subject": "Monthly report",
        "body_text": "Please find attached the report.",
        "attachments": [{"name": "report.pdf.exe", "ext": "exe"}]
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, default_config)
    rule_ids = {r.rule_id for r in res.reasons}
    assert "R-ATT-01" in rule_ids
    assert "R-ATT-02" in rule_ids

def test_case_8_safe_attachment(default_config):
    """Test Case 8: Attachment holiday.pdf triggers no attachment rules."""
    mail_data = {
        "from": {"name": "HR Dept", "address": "hr@partner.com", "domain": "partner.com"},
        "subject": "Holiday list",
        "body_text": "Please find attached the list.",
        "attachments": [{"name": "holiday.pdf", "ext": "pdf"}]
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, default_config)
    rule_ids = {r.rule_id for r in res.reasons}
    assert not any(r.startswith("R-ATT-") for r in rule_ids)

def test_case_9_repeated_keywords_counted_once(default_config):
    """Test Case 9: Same keyword 5 times counted once."""
    mail_data = {
        "from": {"name": "Sender", "address": "sender@domain.com", "domain": "domain.com"},
        "subject": "Important notification",
        "body_text": "urgent urgent urgent urgent urgent please reply."
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, default_config)
    kw_reasons = [r for r in res.reasons if r.rule_id == "R-KW-03"]
    assert len(kw_reasons) == 1

def test_case_10_allow_list_with_dangerous_attachment(default_config):
    """Test Case 10: Sender in allow-list with .exe attachment is not forced to Safe."""
    cfg = dict(default_config)
    cfg["lists"] = {
        "allow_senders": ["trusted_friend@safe.org"],
        "allow_domains": [],
        "block_senders": [],
        "block_domains": [],
        "extra_brands": []
    }
    mail_data = {
        "from": {"name": "Friend", "address": "trusted_friend@safe.org", "domain": "safe.org"},
        "subject": "Look at this game",
        "body_text": "Here is a game",
        "attachments": [{"name": "game.exe", "ext": "exe"}]
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, cfg)
    assert res.score > 0
    rule_ids = {r.rule_id for r in res.reasons}
    assert "R-LST-ALLOW-OVERRIDE" in rule_ids
    assert "R-ATT-01" in rule_ids

def test_case_11_block_list(default_config):
    """Test Case 11: Sender in block-list gets score 100, Spam."""
    cfg = dict(default_config)
    cfg["lists"] = {
        "allow_senders": [],
        "allow_domains": [],
        "block_senders": ["badguy@spammer.com"],
        "block_domains": [],
        "extra_brands": []
    }
    mail_data = {
        "from": {"name": "Bad Guy", "address": "badguy@spammer.com", "domain": "spammer.com"},
        "subject": "Hello",
        "body_text": "Just saying hi"
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, cfg)
    assert res.score == 100
    assert res.label == "spam"
    assert res.reasons[0].rule_id == "R-LST-BLOCK"

def test_case_12_disabled_rule(default_config):
    """Test Case 12: Rule R-URL-02 disabled in config adds no points."""
    cfg = dict(default_config)
    cfg["rules"] = dict(default_config["rules"])
    cfg["rules"]["R-URL-02"] = {"enabled": False, "points": 20}
    
    mail_data = {
        "from": {"name": "Admin", "address": "admin@local.com", "domain": "local.com"},
        "subject": "Server update",
        "body_text": "Check status at http://192.168.1.1/dashboard",
        "urls": [{"href": "http://192.168.1.1/dashboard", "text": "Server"}]
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, cfg)
    rule_ids = {r.rule_id for r in res.reasons}
    assert "R-URL-02" not in rule_ids

def test_case_13_changed_thresholds(default_config):
    """Test Case 13: Thresholds changed to 20 / 40 move label boundaries."""
    cfg = dict(default_config)
    cfg["thresholds"] = {"suspicious": 20, "spam": 40}
    
    mail_data = {
        "from": {"name": "Seller", "address": "sales@promo.com", "domain": "promo.com"},
        "subject": "Claim your prize today",
        "body_text": "You are a winner in our weekly draw.",
        "auth_results": {"spf": "pass"}
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, cfg)
    # With points ~ 24, at threshold 20 it becomes suspicious
    assert res.score >= 20
    assert res.label in ("suspicious", "spam")

def test_case_14_custom_regex_safety():
    """Test Case 14: Custom regex (a+)+$ rejected with validation error."""
    assert is_safe_regex(r"(a+)+$") is False
    assert is_safe_regex(r"(x*)*") is False
    assert is_safe_regex(r"^[a-zA-Z0-9_-]{3,20}$") is True

def test_case_15_obfuscated_keywords(default_config):
    """Test Case 15: Mixed-case 'V1agra', 'v.i.a.g.r.a' triggers R-KW-08."""
    mail_data = {
        "from": {"name": "Pills", "address": "meds@cheapmeds.com", "domain": "cheapmeds.com"},
        "subject": "Discount on v.i.a.g.r.a online",
        "body_text": "Buy v1agra cheap today."
    }
    parsed = to_parsed_email(mail_data)
    res = scan_email(parsed, default_config)
    rule_ids = {r.rule_id for r in res.reasons}
    assert "R-KW-08" in rule_ids or "R-KW-05" in rule_ids
