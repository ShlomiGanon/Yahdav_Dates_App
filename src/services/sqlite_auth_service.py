"""SqliteAuthService — concrete IAuthService over SQLite.

Completely decoupled from the profile and messaging services; it shares only the
`db_path` string. All SQL comes from `sqlite_queries`. Owns the credential table
and the DB-backed "Remember Me" session lifecycle (hash storage, expiry, cleanup).
"""
from __future__ import annotations
import hashlib
import logging
import re
import secrets
import sqlite3
from contextlib import AbstractContextManager
from datetime import datetime, timedelta

from services.I_Auth_Service import IAuthService
from services.sqlite_queries import (
    connection, transaction, AuthQueries, ProfileQueries,
)
from utils.constants import AuthConfig
from utils.timeutils import utcnow_naive
from utils.validation import validate_email, validate_password

log = logging.getLogger(__name__)


class SqliteAuthService(IAuthService):
    """Identity, credentials, and remember-me tokens, backed by SQLite."""

    _USERNAME_RE = re.compile(r"^[A-Za-z0-9_֐-׿][A-Za-z0-9_.\-֐-׿]{2,31}$")

    # Cached real scrypt hash (computed once) used ONLY to burn equivalent CPU
    # on the "user not found" login path, so latency can't reveal account
    # existence (user-enumeration timing oracle).
    _DUMMY_HASH: str | None = None

    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self._initialize()

    def _initialize(self) -> None:
        """Create the auth tables. The profile repository must be initialized
        first (auth_credentials/user_sessions FK user_profiles)."""
        try:
            with self._conn() as c:
                c.executescript(AuthQueries.SCHEMA)
        except sqlite3.Error as e:
            log.exception("auth schema init failed: %s", e)
            raise RuntimeError("auth backend init failed") from e

    # ---- Thread-safe connection seams (delegate to the ledger) ----
    def _conn(self) -> AbstractContextManager[sqlite3.Connection]:
        return connection(self._db_path)

    def _tx(self) -> AbstractContextManager[sqlite3.Connection]:
        return transaction(self._db_path)

    # ============================================================
    #  Hashing helpers
    # ============================================================

    @staticmethod
    def _hash_password(plain: str) -> str:
        salt = secrets.token_bytes(AuthConfig.SCRYPT_SALT_BYTES)
        digest = hashlib.scrypt(
            plain.encode("utf-8"), salt=salt,
            n=AuthConfig.SCRYPT_N, r=AuthConfig.SCRYPT_R,
            p=AuthConfig.SCRYPT_P, dklen=AuthConfig.SCRYPT_DKLEN,
        )
        return f"scrypt${salt.hex()}${digest.hex()}"

    @staticmethod
    def _verify_password(plain: str, stored: str) -> bool:
        try:
            scheme, salt_hex, hash_hex = stored.split("$")
            if scheme != "scrypt":
                return False
            digest = hashlib.scrypt(
                plain.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                n=AuthConfig.SCRYPT_N, r=AuthConfig.SCRYPT_R,
                p=AuthConfig.SCRYPT_P, dklen=AuthConfig.SCRYPT_DKLEN,
            )
            return secrets.compare_digest(digest.hex(), hash_hex)
        except Exception:
            return False

    @classmethod
    def _timing_decoy_hash(cls) -> str:
        if cls._DUMMY_HASH is None:
            cls._DUMMY_HASH = cls._hash_password("\x00timing-decoy-not-a-password\x00")
        return cls._DUMMY_HASH

    @staticmethod
    def _hash_token(token: str) -> str:
        """SHA-256 of a high-entropy device token (no slow KDF needed — it's
        256 bits of CSPRNG output, not a low-entropy password)."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_expired(expires_at: str | None) -> bool:
        """True if the stored expiry is missing, malformed, or in the past.
        Anything unparseable fails CLOSED (treated as expired)."""
        if not expires_at:
            return True
        try:
            expires = datetime.fromisoformat(expires_at)
        except ValueError:
            log.warning("auth: malformed expires_at %r → treating as expired", expires_at)
            return True
        return expires <= utcnow_naive()

    # ============================================================
    #  IAuthService — account lifecycle
    # ============================================================

    def signup_user(self, username: str, email: str, password: str) -> bool:
        if not (self.is_username_valid(username)
                and self.is_email_valid(email)
                and self.is_password_valid(password)):
            return False
        if self.is_username_exists(username) or self.is_email_exists(email):
            return False
        user_id = secrets.token_urlsafe(16)
        now = utcnow_naive().isoformat()
        try:
            # ONE atomic transaction. The minimal profile row is written first
            # because auth_credentials FKs user_profiles; the profile SQL lives
            # in ProfileQueries (the auth service only orchestrates the atomic
            # account creation). A racing duplicate rolls back both inserts.
            with self._tx() as c:
                c.execute(
                    ProfileQueries.INSERT_MINIMAL_PROFILE,
                    ProfileQueries.minimal_profile_params(user_id, username, email, now),
                )
                c.execute(
                    AuthQueries.INSERT_CREDENTIALS,
                    (user_id, username, email, self._hash_password(password), now),
                )
            return True
        except sqlite3.IntegrityError:
            return False
        except sqlite3.Error as e:
            log.exception("signup failed: %s", e)
            return False

    def login_user(self, username_or_email: str, password: str) -> str | None:
        try:
            with self._conn() as c:
                row = c.execute(
                    AuthQueries.SELECT_BY_LOGIN,
                    (username_or_email, username_or_email),
                ).fetchone()
                if row is None:
                    # Equalise latency with the verify path (enumeration guard).
                    self._verify_password(password, self._timing_decoy_hash())
                    return None
                ok = self._verify_password(password, row["password_hash"])
                c.execute(
                    AuthQueries.UPDATE_LOGIN_RESULT,
                    (utcnow_naive().isoformat(), ok, row["user_id"]),
                )
                return row["user_id"] if ok else None
        except sqlite3.Error as e:
            log.exception("login failed: %s", e)
            return None

    def is_username_exists(self, username: str) -> bool:
        try:
            with self._conn() as c:
                return c.execute(
                    AuthQueries.EXISTS_BY_USERNAME, (username,),
                ).fetchone() is not None
        except sqlite3.Error as e:
            log.exception("username existence check failed: %s", e)
            return False

    def is_email_exists(self, email: str) -> bool:
        try:
            with self._conn() as c:
                return c.execute(
                    AuthQueries.EXISTS_BY_EMAIL, (email,),
                ).fetchone() is not None
        except sqlite3.Error as e:
            log.exception("email existence check failed: %s", e)
            return False

    @staticmethod
    def is_email_valid(email: str) -> bool:
        return bool(email) and validate_email(email)

    @staticmethod
    def is_username_valid(username: str) -> bool:
        return bool(username) and bool(SqliteAuthService._USERNAME_RE.match(username))

    @staticmethod
    def is_password_valid(password: str) -> bool:
        return bool(password) and validate_password(password)

    # ============================================================
    #  IAuthService — remember-me tokens (DB-backed sessions)
    # ============================================================

    def generate_remember_me_token(self, user_id: str) -> str:
        if not user_id:
            raise ValueError("user_id is required")
        token = secrets.token_urlsafe(AuthConfig.REMEMBER_ME_TOKEN_BYTES)
        now = utcnow_naive()
        expires_at = now + timedelta(days=AuthConfig.REMEMBER_ME_DAYS)
        try:
            with self._conn() as c:
                # Opportunistic cleanup of dead rows, then store the HASH (never
                # the raw token). One row per device.
                c.execute(AuthQueries.DELETE_EXPIRED_SESSIONS, (now.isoformat(),))
                c.execute(
                    AuthQueries.INSERT_SESSION,
                    (self._hash_token(token), user_id,
                     now.isoformat(), expires_at.isoformat()),
                )
            return token
        except sqlite3.IntegrityError as e:
            log.warning("remember-me token rejected user=%s: %s", user_id, e)
            raise ValueError("user_id does not exist") from e
        except sqlite3.Error as e:
            log.exception("generate_remember_me_token failed user=%s: %s", user_id, e)
            raise RuntimeError("failed to generate remember-me token") from e

    def validate_remember_me_token(self, token: str) -> str | None:
        if not token:
            return None
        token_hash = self._hash_token(token)
        try:
            with self._conn() as c:
                row = c.execute(AuthQueries.SELECT_SESSION, (token_hash,)).fetchone()
                if row is None:
                    log.info("validate: no session row for presented token")
                    return None
                if self._is_expired(row["expires_at"]):
                    # Self-clean the dead row so it can't be re-evaluated.
                    c.execute(AuthQueries.DELETE_SESSION, (token_hash,))
                    log.info("validate: token expired → purged row")
                    return None
                return row["user_id"]
        except sqlite3.Error as e:
            # Read path: a storage hiccup must not crash boot — fail closed.
            log.exception("validate_remember_me_token failed: %s", e)
            return None

    def revoke_remember_me_token(self, token: str) -> None:
        if not token:
            return  # idempotent
        try:
            with self._conn() as c:
                c.execute(AuthQueries.DELETE_SESSION, (self._hash_token(token),))
        except sqlite3.Error as e:
            log.exception("revoke_remember_me_token failed: %s", e)
            raise RuntimeError("failed to revoke remember-me token") from e
