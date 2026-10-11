from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple

class MailProvider(ABC):
    key: str # "gmail" | "outlook" | "yahoo" | "icloud" | "mock"

    def __init__(self, account: Dict[str, Any]):
        self.account = account
        self.user_id = account.get("user_id")
        self.address = account.get("address", "")
        self.sync_state = account.get("sync_state", {})

    @abstractmethod
    def connect_url(self, state: str) -> Optional[str]:
        """Generate OAuth authorization URL, or None for app-password providers."""
        pass

    @abstractmethod
    def finish_connect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Exchange auth code or validate credentials, returning {credentials, address}."""
        pass

    @abstractmethod
    def list_page(self, since_days: int, cursor: Optional[str], limit: int) -> Tuple[List[str], Optional[str]]:
        """Return (list_of_message_ids, next_cursor)."""
        pass

    @abstractmethod
    def get_message(self, msg_id: str) -> Dict[str, Any]:
        """Fetch and return a normalized mail dictionary."""
        pass

    @abstractmethod
    def fetch_new(self) -> List[Dict[str, Any]]:
        """Fetch only messages newer than stored sync_state."""
        pass

    @abstractmethod
    def start_watch(self) -> None:
        """Initialize webhook / Pub/Sub / push subscription."""
        pass

    @abstractmethod
    def stop_watch(self) -> None:
        """Terminate active watch or subscription."""
        pass

    @abstractmethod
    def get_html(self, msg_id: str) -> Optional[str]:
        """Fetch raw HTML body for sandboxed rendering in detail drawer."""
        pass

    @abstractmethod
    def revoke(self) -> None:
        """Revoke tokens at the remote provider upon mailbox disconnection."""
        pass
