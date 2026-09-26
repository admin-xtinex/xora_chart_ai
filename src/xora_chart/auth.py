"""User accounts, password hashing and login sessions for the dashboard.

Users and sessions live in their own JSON file next to the state snapshot
(persistent ``/home`` storage on App Service), written immediately because
changes are rare.  Passwords are salted scrypt hashes; session tokens are
random and only their SHA-256 digest is stored.

The first admin is created from ``XORA_ADMIN_USERNAME`` / ``XORA_ADMIN_PASSWORD``
when no users exist yet.  ``XORA_SEED_USERS`` (a JSON list of
``{"username", "password", "role"}``) creates any listed users that don't exist;
existing users are never modified.  Both are meant to be removed after use.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ROLES = ("admin", "user")
MIN_PASSWORD_LENGTH = 8
SESSION_TTL_SECONDS = 7 * 24 * 3600
MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 300
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.@-]{3,64}$")

# scrypt cost: ~50 ms per hash on a small vCPU, 16 MiB memory.
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


class AuthError(RuntimeError):
    """Raised for any authentication/authorization failure (message is user-safe)."""


def _users_path() -> Path:
    configured = os.getenv("XORA_USERS_FILE")
    if configured:
        return Path(configured)
    state = Path(os.getenv("XORA_STATE_FILE", "state/xora_state.json"))
    return state.parent / "users.json"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, dklen=32, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex), dklen=32, n=int(n), r=int(r), p=int(p)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _validate_password(password: str) -> None:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > 256:
        raise AuthError("Password is too long")


def _validate_username(username: str) -> str:
    name = str(username or "").strip()
    if not _USERNAME_RE.match(name):
        raise AuthError("Username must be 3-64 characters: letters, digits, . _ @ -")
    return name


class UserStore:
    _instance: "UserStore | None" = None
    _lock = threading.Lock()

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _users_path()
        self._io_lock = threading.RLock()
        self._users: dict[str, dict[str, Any]] = {}
        self._sessions: dict[str, dict[str, Any]] = {}
        self._failures: dict[str, tuple[int, float]] = {}
        self._load()
        self._bootstrap_admin()
        self._seed_users()

    @classmethod
    def instance(cls) -> "UserStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = UserStore()
        return cls._instance

    # ---------- persistence ----------
    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except Exception:
            log.exception("Could not read users file %s", self._path)
            return
        self._users = {u["username"].lower(): u for u in raw.get("users", []) if u.get("username")}
        now = time.time()
        self._sessions = {k: v for k, v in (raw.get("sessions") or {}).items() if v.get("expires", 0) > now}

    def _save(self) -> None:
        with self._io_lock:
            payload = {"users": list(self._users.values()), "sessions": self._sessions}
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
            tmp.replace(self._path)

    def _bootstrap_admin(self) -> None:
        if self._users:
            return
        username = os.getenv("XORA_ADMIN_USERNAME", "").strip()
        password = os.getenv("XORA_ADMIN_PASSWORD", "")
        if not username or not password:
            log.warning("No users exist and XORA_ADMIN_USERNAME/XORA_ADMIN_PASSWORD are not set; login is impossible")
            return
        try:
            self.create_user(username, password, role="admin")
            log.info("Bootstrapped admin user %s", username)
        except AuthError as exc:
            log.error("Admin bootstrap failed: %s", exc)

    def _seed_users(self) -> None:
        raw = os.getenv("XORA_SEED_USERS", "").strip()
        if not raw:
            return
        try:
            entries = json.loads(raw)
            if not isinstance(entries, list):
                raise ValueError("expected a JSON list")
        except ValueError as exc:
            log.error("XORA_SEED_USERS is not valid JSON: %s", exc)
            return
        for entry in entries:
            name = str((entry or {}).get("username") or "")
            if name.lower() in self._users:
                continue
            try:
                self.create_user(name, str(entry.get("password") or ""), str(entry.get("role") or "user"))
                log.info("Seeded user %s", name)
            except AuthError as exc:
                log.error("Seeding user %r failed: %s", name, exc)

    # ---------- public API ----------
    @staticmethod
    def public(user: dict[str, Any]) -> dict[str, Any]:
        return {
            "username": user["username"],
            "role": user.get("role", "user"),
            "created_at": user.get("created_at"),
            "last_login_at": user.get("last_login_at"),
        }

    def has_users(self) -> bool:
        return bool(self._users)

    def list_users(self) -> list[dict[str, Any]]:
        return [self.public(u) for u in sorted(self._users.values(), key=lambda u: u["username"].lower())]

    def create_user(self, username: str, password: str, role: str = "user") -> dict[str, Any]:
        name = _validate_username(username)
        if role not in ROLES:
            raise AuthError("Role must be admin or user")
        _validate_password(password)
        if name.lower() in self._users:
            raise AuthError("A user with that name already exists")
        user = {
            "username": name,
            "role": role,
            "password_hash": hash_password(password),
            "created_at": int(time.time()),
            "last_login_at": None,
        }
        self._users[name.lower()] = user
        self._save()
        return self.public(user)

    def delete_user(self, username: str, *, acting: str) -> None:
        key = str(username or "").lower()
        if key not in self._users:
            raise AuthError("User not found")
        if key == acting.lower():
            raise AuthError("You cannot delete your own account")
        if self._users[key].get("role") == "admin" and sum(1 for u in self._users.values() if u.get("role") == "admin") <= 1:
            raise AuthError("Cannot delete the last admin")
        del self._users[key]
        self._sessions = {k: v for k, v in self._sessions.items() if v.get("user") != key}
        self._save()

    def set_password(self, username: str, new_password: str, *, revoke_sessions: bool = True, keep: str | None = None) -> None:
        key = str(username or "").lower()
        user = self._users.get(key)
        if not user:
            raise AuthError("User not found")
        _validate_password(new_password)
        user["password_hash"] = hash_password(new_password)
        if revoke_sessions:
            self._sessions = {
                k: v for k, v in self._sessions.items() if v.get("user") != key or (keep and k == keep)
            }
        self._save()

    def change_password(self, username: str, current: str, new_password: str, *, token: str) -> None:
        user = self._users.get(username.lower())
        if not user or not verify_password(current or "", user["password_hash"]):
            raise AuthError("Current password is incorrect")
        # Sign out other devices, keep this one.
        self.set_password(username, new_password, keep=_token_digest(token))

    def login(self, username: str, password: str) -> tuple[str, dict[str, Any]]:
        key = str(username or "").strip().lower()
        count, since = self._failures.get(key, (0, 0.0))
        if count >= MAX_FAILED_LOGINS and time.time() - since < LOCKOUT_SECONDS:
            raise AuthError("Too many failed attempts. Try again in a few minutes.")
        user = self._users.get(key)
        # Hash even for unknown users so response time doesn't reveal which names exist.
        ok = verify_password(password or "", user["password_hash"] if user else hash_password("x"))
        if not user or not ok:
            self._failures[key] = (count + 1 if time.time() - since < LOCKOUT_SECONDS else 1, time.time())
            raise AuthError("Invalid username or password")
        self._failures.pop(key, None)
        token = secrets.token_urlsafe(32)
        now = time.time()
        self._sessions[_token_digest(token)] = {"user": key, "created": now, "expires": now + SESSION_TTL_SECONDS}
        self._sessions = {k: v for k, v in self._sessions.items() if v.get("expires", 0) > now}
        user["last_login_at"] = int(now)
        self._save()
        return token, self.public(user)

    def resume(self, token: str) -> dict[str, Any]:
        session = self._sessions.get(_token_digest(str(token or "")))
        if not session or session.get("expires", 0) <= time.time():
            raise AuthError("Session expired. Please sign in again.")
        user = self._users.get(session["user"])
        if not user:
            raise AuthError("Session expired. Please sign in again.")
        return self.public(user)

    def logout(self, token: str) -> None:
        if self._sessions.pop(_token_digest(str(token or "")), None) is not None:
            self._save()
