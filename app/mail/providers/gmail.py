import datetime
import base64
import requests
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
from .base import MailProvider
from .mock import MockMailProvider
from ...security import decrypt_data

class GmailProvider(MailProvider):
    key = "gmail"

    def __init__(self, account: Dict[str, Any]):
        super().__init__(account)
        self.creds = {}
        if account.get("credentials_enc"):
            try:
                self.creds = decrypt_data(account["credentials_enc"])
            except Exception:
                self.creds = {}
        self.access_token = self.creds.get("token")
        self.fallback = MockMailProvider(account)

    def _is_real_token(self) -> bool:
        return bool(self.access_token and self.access_token != "mock_oauth_token" and not self.access_token.startswith("mock_"))

    def _refresh_access_token(self) -> bool:
        refresh_token = self.creds.get("refresh_token")
        if not refresh_token:
            return False
        try:
            from flask import current_app
            client_id = current_app.config.get("GOOGLE_CLIENT_ID")
            client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET")
            if not (client_id and client_secret):
                return False

            resp = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                },
                timeout=10
            )
            if resp.status_code == 200:
                token_data = resp.json()
                new_token = token_data.get("access_token")
                if new_token:
                    self.access_token = new_token
                    self.creds["token"] = new_token
                    from ...security import encrypt_data
                    from ...db import mail_accounts_col
                    if self.account.get("_id"):
                        mail_accounts_col().update_one(
                            {"_id": self.account["_id"]},
                            {"$set": {"credentials_enc": encrypt_data(self.creds)}}
                        )
                    return True
        except Exception:
            pass
        return False

    def connect_url(self, state: str) -> Optional[str]:
        return None

    def finish_connect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def list_page(self, since_days: int = 30, cursor: Optional[str] = None, limit: int = 50) -> Tuple[List[str], Optional[str]]:
        if not self._is_real_token():
            return self.fallback.list_page(since_days, cursor, limit)

        try:
            url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
            params = {"maxResults": limit}
            if cursor:
                params["pageToken"] = cursor

            headers = {"Authorization": f"Bearer {self.access_token}"}
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 401:
                # Token expired, refresh and retry once
                if self._refresh_access_token():
                    headers = {"Authorization": f"Bearer {self.access_token}"}
                    res = requests.get(url, headers=headers, params=params, timeout=10)

            if res.status_code == 200:
                data = res.json()
                messages = data.get("messages", [])
                msg_ids = [m["id"] for m in messages]
                next_page = data.get("nextPageToken")
                return msg_ids, next_page
            else:
                return self.fallback.list_page(since_days, cursor, limit)
        except Exception:
            return self.fallback.list_page(since_days, cursor, limit)

    def get_message(self, msg_id: str) -> Dict[str, Any]:
        if not self._is_real_token() or msg_id.startswith("mock_"):
            return self.fallback.get_message(msg_id)

        try:
            url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=full"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 401:
                if self._refresh_access_token():
                    headers = {"Authorization": f"Bearer {self.access_token}"}
                    res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                return self.fallback.get_message(msg_id)

            data = res.json()
            payload = data.get("payload", {})
            headers_list = payload.get("headers", [])
            header_map = {h["name"].lower(): h["value"] for h in headers_list}

            # Parse from
            from_raw = header_map.get("from", "")
            from_name = from_raw
            from_addr = from_raw
            if "<" in from_raw and ">" in from_raw:
                from_name = from_raw.split("<")[0].strip().strip('"')
                from_addr = from_raw.split("<")[1].split(">")[0].strip()

            subject = header_map.get("subject", "(No Subject)")
            date_raw = header_map.get("date", "")
            
            # Auth headers
            spf_val = "neutral"
            dkim_val = "neutral"
            dmarc_val = "neutral"
            auth_res = header_map.get("authentication-results", "").lower()
            if "spf=pass" in auth_res:
                spf_val = "pass"
            elif "spf=fail" in auth_res:
                spf_val = "fail"
                
            if "dkim=pass" in auth_res:
                dkim_val = "pass"
            elif "dkim=fail" in auth_res:
                dkim_val = "fail"

            if "dmarc=pass" in auth_res:
                dmarc_val = "pass"
            elif "dmarc=fail" in auth_res:
                dmarc_val = "fail"

            # Parse body
            body_text = ""
            def extract_body(p):
                text = ""
                mime = p.get("mimeType", "")
                if mime == "text/plain" and "data" in p.get("body", {}):
                    try:
                        raw = base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="ignore")
                        text += raw
                    except Exception:
                        pass
                elif mime == "text/html" and "data" in p.get("body", {}):
                    try:
                        raw = base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="ignore")
                        soup = BeautifulSoup(raw, "html.parser")
                        text += soup.get_text(separator=" ")
                    except Exception:
                        pass
                for subpart in p.get("parts", []):
                    text += " " + extract_body(subpart)
                return text

            body_text = extract_body(payload).strip()
            if not body_text:
                body_text = data.get("snippet", "")

            # Attachments
            attachments = []
            for part in payload.get("parts", []):
                fname = part.get("filename")
                if fname:
                    attachments.append({
                        "filename": fname,
                        "content_type": part.get("mimeType", "application/octet-stream"),
                        "size_bytes": part.get("body", {}).get("size", 0)
                    })

            # Received date
            internal_date_ms = data.get("internalDate")
            if internal_date_ms:
                dt = datetime.datetime.fromtimestamp(int(internal_date_ms) / 1000.0, tz=datetime.timezone.utc)
                iso_date = dt.isoformat()
            else:
                iso_date = datetime.datetime.now(datetime.timezone.utc).isoformat()

            return {
                "provider_msg_id": msg_id,
                "message_id_header": header_map.get("message-id", f"<{msg_id}@mail.gmail.com>"),
                "from": {"name": from_name, "address": from_addr},
                "to": [{"name": "", "address": header_map.get("to", "")}],
                "reply_to": {"name": "", "address": header_map.get("reply-to", "")},
                "subject": subject,
                "snippet": data.get("snippet", ""),
                "body_text": body_text,
                "urls": [],
                "attachments": attachments,
                "auth_results": {
                    "spf": spf_val,
                    "dkim": dkim_val,
                    "dmarc": dmarc_val,
                    "header": auth_res
                },
                "received_at": iso_date,
                "is_read": "UNREAD" not in data.get("labelIds", [])
            }
        except Exception:
            return self.fallback.get_message(msg_id)

    def fetch_new(self) -> List[Dict[str, Any]]:
        msg_ids, _ = self.list_page(limit=10)
        return [self.get_message(mid) for mid in msg_ids if mid]

    def start_watch(self) -> None:
        pass

    def stop_watch(self) -> None:
        pass

    def get_html(self, msg_id: str) -> Optional[str]:
        return self.fallback.get_html(msg_id)

    def revoke(self) -> None:
        pass
