import datetime
from typing import List, Dict, Any, Optional, Tuple
from .base import MailProvider

MOCK_FIXTURES: Dict[str, List[Dict[str, Any]]] = {
    "gmail": [
        {
            "provider_msg_id": "gm_001",
            "message_id_header": "<paypal.service.alert.001@mail.gmail.com>",
            "from": {"name": "PayPal Support", "address": "service@paypa1-security.top", "domain": "paypa1-security.top"},
            "to": [{"name": "User", "address": "user@gmail.com"}],
            "reply_to": {"name": "PayPal Support", "address": "collect@free-mail.example"},
            "subject": "Verify your account immediately",
            "snippet": "Dear customer, your account has been temporarily restricted due to suspicious sign-in attempts...",
            "body_text": "Dear customer,\n\nYour account has been temporarily restricted due to suspicious sign-in attempts. Please click http://203.0.113.9/login to confirm your identity within 24 hours to prevent account closure.\n\nThank you,\nPayPal Security Team",
            "urls": [
                {"href": "http://203.0.113.9/login", "text": "www.paypal.com", "host": "203.0.113.9", "scheme": "http"}
            ],
            "attachments": [
                {"name": "security_details.pdf.exe", "ext": "exe", "size": 48211, "mime": "application/octet-stream"}
            ],
            "auth_results": {"spf": "fail", "dkim": "none", "dmarc": "fail"},
            "received_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "is_read": False
        },
        {
            "provider_msg_id": "gm_002",
            "message_id_header": "<microsoft.security.alert.882@microsoft.com>",
            "from": {"name": "Microsoft", "address": "account-security@microsoft.com", "domain": "microsoft.com"},
            "to": [{"name": "User", "address": "user@gmail.com"}],
            "reply_to": {"name": "", "address": "account-security@microsoft.com"},
            "subject": "Your account security information",
            "snippet": "Security info was recently accessed for your Microsoft account. If this was you, you can safely ignore this...",
            "body_text": "Hi,\n\nThe security info for your Microsoft account was recently accessed from a trusted device. If you did this, you do not need to take any action.\n\nMicrosoft Security Team",
            "urls": [
                {"href": "https://account.microsoft.com", "text": "Account Security", "host": "microsoft.com", "scheme": "https"}
            ],
            "attachments": [],
            "auth_results": {"spf": "pass", "dkim": "pass", "dmarc": "pass"},
            "received_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=45)).isoformat(),
            "is_read": True
        },
        {
            "provider_msg_id": "gm_003",
            "message_id_header": "<netflix.billing.notice.912@netflix-renewal.xyz>",
            "from": {"name": "Netflix", "address": "support@netflix-renewal.xyz", "domain": "netflix-renewal.xyz"},
            "to": [{"name": "User", "address": "user@gmail.com"}],
            "reply_to": {"name": "", "address": "support@netflix-renewal.xyz"},
            "subject": "Your payment method has expired",
            "snippet": "We were unable to process your payment for the next billing cycle. Please update payment immediately...",
            "body_text": "Dear subscriber,\n\nYour payment method has expired. Please update your billing information at https://bit.ly/netflix-renew within 48 hours to prevent account suspension.\n\nNetflix Support",
            "urls": [
                {"href": "https://bit.ly/netflix-renew", "text": "Update Payment", "host": "bit.ly", "scheme": "https"}
            ],
            "attachments": [],
            "auth_results": {"spf": "pass", "dkim": "none", "dmarc": "none"},
            "received_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1, minutes=15)).isoformat(),
            "is_read": False
        },
        {
            "provider_msg_id": "gm_004",
            "message_id_header": "<admin.exams.notice.019@college.edu>",
            "from": {"name": "College Admin", "address": "academic-office@college.edu", "domain": "college.edu"},
            "to": [{"name": "User", "address": "user@gmail.com"}],
            "reply_to": {"name": "", "address": "academic-office@college.edu"},
            "subject": "Tomorrow's examination schedule",
            "snippet": "Please find attached the finalized examination hall schedule for tomorrow morning...",
            "body_text": "Dear Students,\n\nPlease review tomorrow's finalized examination hall allocations. Remember to carry your student identity card.\n\nAcademic Office",
            "urls": [],
            "attachments": [
                {"name": "exam_schedule_hall_a.pdf", "ext": "pdf", "size": 182400, "mime": "application/pdf"}
            ],
            "auth_results": {"spf": "pass", "dkim": "pass", "dmarc": "pass"},
            "received_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2, minutes=30)).isoformat(),
            "is_read": True
        },
        {
            "provider_msg_id": "gm_005",
            "message_id_header": "<amazon.orders.9821@amazon.com>",
            "from": {"name": "Amazon Shipping", "address": "shipment-tracking@amazon.com", "domain": "amazon.com"},
            "to": [{"name": "User", "address": "user@gmail.com"}],
            "reply_to": {"name": "", "address": "no-reply@amazon.com"},
            "subject": "Your Amazon order #402-9812 has shipped",
            "snippet": "Good news! Your package is on its way. Track your package at https://amazon.com/orders/track...",
            "body_text": "Hello,\n\nYour recent order #402-9812 has shipped and will arrive on Monday. Track your delivery at https://amazon.com/orders/track.\n\nThank you for shopping with us.",
            "urls": [
                {"href": "https://amazon.com/orders/track", "text": "Track Package", "host": "amazon.com", "scheme": "https"}
            ],
            "attachments": [],
            "auth_results": {"spf": "pass", "dkim": "pass", "dmarc": "pass"},
            "received_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)).isoformat(),
            "is_read": True
        }
    ],
    "outlook": [
        {
            "provider_msg_id": "ol_001",
            "message_id_header": "<prize.reward.center@promo-win.example>",
            "from": {"name": "Prize Center", "address": "rewards@promo-win.example", "domain": "promo-win.example"},
            "to": [{"name": "User", "address": "user@outlook.com"}],
            "reply_to": {"name": "", "address": "rewards@promo-win.example"},
            "subject": "You are a winner - claim your reward today",
            "snippet": "Congratulations! You have won our weekly cash sweepstakes. Claim your prize immediately at https://bit.ly/x1...",
            "body_text": "Congratulations winner!\n\nYou have been selected to receive a cash prize. Claim your reward at https://bit.ly/x1 before it expires.",
            "urls": [
                {"href": "https://bit.ly/x1", "text": "Claim Prize Here", "host": "bit.ly", "scheme": "https"}
            ],
            "attachments": [],
            "auth_results": {"spf": "pass", "dkim": "none", "dmarc": "none"},
            "received_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat() + "Z",
            "is_read": False
        },
        {
            "provider_msg_id": "ol_002",
            "message_id_header": "<hr.payroll.team@company.com>",
            "from": {"name": "Corporate Payroll", "address": "payroll@company.com", "domain": "company.com"},
            "to": [{"name": "User", "address": "user@outlook.com"}],
            "reply_to": {"name": "", "address": "payroll@company.com"},
            "subject": "Monthly Paystub and Tax Withholding",
            "snippet": "Please find attached your monthly salary slip and withholding documentation for your records...",
            "body_text": "Dear Employee,\n\nYour salary statement for this period has been processed. Please review the attached document.",
            "urls": [],
            "attachments": [
                {"name": "paystub_october.pdf", "ext": "pdf", "size": 128400, "mime": "application/pdf"}
            ],
            "auth_results": {"spf": "pass", "dkim": "pass", "dmarc": "pass"},
            "received_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).isoformat() + "Z",
            "is_read": True
        }
    ],
    "yahoo": [
        {
            "provider_msg_id": "yh_001",
            "message_id_header": "<newsletter@techdigest.io>",
            "from": {"name": "Tech Digest", "address": "editor@techdigest.io", "domain": "techdigest.io"},
            "to": [{"name": "User", "address": "user@yahoo.com"}],
            "reply_to": {"name": "", "address": "editor@techdigest.io"},
            "subject": "This Week in Cybersecurity & AI",
            "snippet": "The top 5 security vulnerabilities patched this week and new developer productivity guidelines...",
            "body_text": "Welcome to this week's Tech Digest!\n\nRead our deep-dive analysis on deterministic rule engine design at https://techdigest.io/articles/rules.\n\nYou can unsubscribe anytime at https://techdigest.io/unsubscribe.",
            "urls": [
                {"href": "https://techdigest.io/articles/rules", "text": "Read Article", "host": "techdigest.io", "scheme": "https"},
                {"href": "https://techdigest.io/unsubscribe", "text": "Unsubscribe", "host": "techdigest.io", "scheme": "https"}
            ],
            "attachments": [],
            "auth_results": {"spf": "pass", "dkim": "pass", "dmarc": "pass"},
            "received_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).isoformat() + "Z",
            "is_read": False
        }
    ],
    "icloud": [
        {
            "provider_msg_id": "ic_001",
            "message_id_header": "<apple.support.id.9912@icloud-billing.click>",
            "from": {"name": "Apple Billing Support", "address": "billing-alert@icloud-billing.click", "domain": "icloud-billing.click"},
            "to": [{"name": "User", "address": "user@icloud.com"}],
            "reply_to": {"name": "", "address": "billing-alert@icloud-billing.click"},
            "subject": "Action Required: Your iCloud storage has been suspended",
            "snippet": "Your Apple ID has been suspended due to an unpaid storage bill. Update payment immediately...",
            "body_text": "Security Alert:\n\nYour iCloud subscription expired. Click https://appleid.apple.com.billing-auth.click/login to verify your credit card details immediately.",
            "urls": [
                {"href": "https://appleid.apple.com.billing-auth.click/login", "text": "Verify Apple ID", "host": "appleid.apple.com.billing-auth.click", "scheme": "https"}
            ],
            "attachments": [],
            "auth_results": {"spf": "fail", "dkim": "none", "dmarc": "fail"},
            "received_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)).isoformat() + "Z",
            "is_read": False
        }
    ]
}

class MockMailProvider(MailProvider):
    def __init__(self, account: Dict[str, Any]):
        super().__init__(account)
        self.key = account.get("provider", "gmail")

    def connect_url(self, state: str) -> Optional[str]:
        return f"/api/mail/connect/{self.key}/callback?code=mock_code&state={state}"

    def finish_connect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "credentials": {"token": "mock_token_123", "type": "mock"},
            "address": self.account.get("address") or f"demo_user@{self.key}.com"
        }

    def list_page(self, since_days: int, cursor: Optional[str], limit: int) -> Tuple[List[str], Optional[str]]:
        fixtures = MOCK_FIXTURES.get(self.key, [])
        ids = [m["provider_msg_id"] for m in fixtures]
        return ids, None

    def get_message(self, msg_id: str) -> Dict[str, Any]:
        fixtures = MOCK_FIXTURES.get(self.key, [])
        for f in fixtures:
            if f["provider_msg_id"] == msg_id:
                return f
        # Return fallback dummy
        return {
            "provider_msg_id": msg_id,
            "message_id_header": f"<{msg_id}@mail.mock>",
            "from": {"name": "Test Sender", "address": "test@example.com", "domain": "example.com"},
            "subject": "Test Message",
            "snippet": "Test body snippet",
            "body_text": "Test body message",
            "urls": [],
            "attachments": [],
            "auth_results": {"spf": "pass", "dkim": "pass", "dmarc": "pass"},
            "received_at": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            "is_read": True
        }

    def fetch_new(self) -> List[Dict[str, Any]]:
        return MOCK_FIXTURES.get(self.key, [])

    def start_watch(self) -> None:
        pass

    def stop_watch(self) -> None:
        pass

    def get_html(self, msg_id: str) -> Optional[str]:
        msg = self.get_message(msg_id)
        body = msg.get("body_text", "").replace("\n", "<br>")
        return f"<div style='font-family:sans-serif; padding:16px;'><h3>{msg.get('subject')}</h3><p>{body}</p></div>"

    def revoke(self) -> None:
        pass
