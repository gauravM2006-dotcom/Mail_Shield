from flask_login import UserMixin
from typing import Dict, Any, Optional, List
from datetime import datetime

class User(UserMixin):
    def __init__(
        self,
        id: str,
        username: str,
        email: str,
        email_verified: bool = False,
        password_hash: Optional[str] = None,
        display_name: str = "",
        avatar_url: str = "",
        identities: Optional[List[Dict[str, Any]]] = None,
        status: str = "active",
        failed_logins: int = 0,
        locked_until: Optional[datetime] = None
    ):
        self.id = str(id)
        self.username = username
        self.email = email
        self.email_verified = email_verified
        self.password_hash = password_hash
        self.display_name = display_name or username
        self.avatar_url = avatar_url
        self.identities = identities or []
        self.status = status
        self.failed_logins = failed_logins
        self.locked_until = locked_until

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "User":
        return cls(
            id=str(doc.get("_id")),
            username=doc.get("username", ""),
            email=doc.get("email", ""),
            email_verified=doc.get("email_verified", False),
            password_hash=doc.get("password_hash"),
            display_name=doc.get("display_name", doc.get("username", "")),
            avatar_url=doc.get("avatar_url", ""),
            identities=doc.get("identities", []),
            status=doc.get("status", "active"),
            failed_logins=doc.get("failed_logins", 0),
            locked_until=doc.get("locked_until")
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "email_verified": self.email_verified,
            "has_password": self.password_hash is not None,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "identities": self.identities,
            "status": self.status
        }
