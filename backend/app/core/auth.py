import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database.session import get_db
from backend.app.models.organization import Membership, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
ROLES = {"admin", "reviewer", "accountant", "viewer"}
PERMISSIONS = {
    "admin": {"read", "review", "approve", "accounting", "manual_expense", "manage_users"},
    "reviewer": {"read", "review", "approve"},
    "accountant": {"read", "accounting", "manual_expense"},
    "viewer": {"read"},
}


def hash_password(password: str) -> str:
    if not password or len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    try:
        from argon2 import PasswordHasher
        return "argon2id$" + PasswordHasher().hash(password)
    except ImportError:
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return "scrypt$" + base64.urlsafe_b64encode(salt + digest).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        if encoded.startswith("argon2id$"):
            from argon2 import PasswordHasher
            return PasswordHasher().verify(encoded.removeprefix("argon2id$"), password)
        if encoded.startswith("scrypt$"):
            raw = base64.urlsafe_b64decode(encoded.removeprefix("scrypt$").encode())
            return hmac.compare_digest(hashlib.scrypt(password.encode(), salt=raw[:16], n=2**14, r=8, p=1), raw[16:])
    except Exception:
        return False
    return False


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def create_access_token(user_id: UUID, organization_id: UUID, role: str) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({"sub": str(user_id), "org": str(organization_id), "role": role, "exp": int(time.time()) + settings.access_token_minutes * 60}, separators=(",", ":")).encode())
    body = f"{header}.{payload}"
    signature = _b64(hmac.new(settings.auth_secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


@dataclass(frozen=True)
class CurrentUser:
    user: User
    membership: Membership

    @property
    def organization_id(self) -> UUID:
        return self.membership.organization_id


def current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> CurrentUser:
    try:
        header, payload, signature = token.split(".")
        body = f"{header}.{payload}"
        expected = _b64(hmac.new(settings.auth_secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(data["exp"]) <= int(time.time()):
            raise ValueError
        user = db.get(User, UUID(data["sub"]))
        membership = db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.organization_id == UUID(data["org"]))) if user else None
        if not user or not user.is_active or not membership or membership.role != data["role"]:
            raise ValueError
        return CurrentUser(user, membership)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired credentials") from None


def require_permission(permission: str):
    def dependency(actor: CurrentUser = Depends(current_user)) -> CurrentUser:
        if permission not in PERMISSIONS.get(actor.membership.role, set()):
            raise HTTPException(status_code=403, detail="insufficient organization permission")
        return actor
    return dependency
