"""Centralized SQL ledger for the SQLite persistence layer.

Every raw SQL string, DDL statement, index, UPSERT, pragma, and the
connection/transaction wrappers live HERE and only here. The three concrete
services (`SqliteAuthService`, `SqliteProfileRepository`, `SqliteMessagingService`)
reference these strings/helpers and contain ZERO inline SQL.

Layout:
  • `connection(db_path)` / `transaction(db_path)` — thread-safe connection
    context managers; pragmas applied on EVERY connection.
  • `AuthQueries`     — auth_credentials + user_sessions (DDL + DML).
  • `ProfileQueries`  — user_profiles + user_blocks (DDL + DML + minimal row).
  • `MessagingQueries`— direct_messages (DDL + DML).
"""
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from utils.constants import DBConfig, AssetPaths
from models.user_profile import AccountStatus, Gender


# ============================================================================
#  Connection & transaction infrastructure (constraints #2 and #4)
# ============================================================================

# Applied on EVERY freshly-opened connection. foreign_keys is per-connection
# (must be re-asserted each time); journal_mode/synchronous are persistent but
# harmless to re-issue.
_PRAGMAS: tuple[str, ...] = (
    "PRAGMA foreign_keys = ON",
    f"PRAGMA journal_mode = {DBConfig.JOURNAL_MODE}",
    f"PRAGMA synchronous = {DBConfig.SYNCHRONOUS}",
    f"PRAGMA busy_timeout = {DBConfig.BUSY_TIMEOUT_MS}",
)


@contextmanager
def connection(db_path: str) -> Iterator[sqlite3.Connection]:
    """Open a FRESH connection, apply pragmas, yield it, and ALWAYS close it.

    A brand-new connection per call (never a shared/persistent one) is what
    makes the services safe to call from `asyncio.to_thread` — no connection
    object ever crosses a thread boundary, and the `finally` guarantees the
    handle is released even if the body raises mid-query.
    """
    conn = sqlite3.connect(
        db_path,
        isolation_level=DBConfig.ISOLATION_LEVEL,   # autocommit; we manage txns
        timeout=DBConfig.CONNECT_TIMEOUT_SEC,
    )
    try:
        conn.row_factory = sqlite3.Row
        for pragma in _PRAGMAS:
            conn.execute(pragma)
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(db_path: str) -> Iterator[sqlite3.Connection]:
    """`connection()` wrapped in an explicit BEGIN/COMMIT/ROLLBACK.

    Connections run in autocommit mode, so a multi-statement write (e.g. signup's
    profile + credentials inserts) must be wrapped to be all-or-nothing.
    """
    with connection(db_path) as conn:
        conn.execute("BEGIN")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")


# ============================================================================
#  Auth — credentials + remember-me sessions
# ============================================================================

class AuthQueries:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS auth_credentials (
        user_id         TEXT PRIMARY KEY,
        username        TEXT NOT NULL UNIQUE COLLATE NOCASE,
        email           TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash   TEXT NOT NULL,        -- 'scrypt$<salt_hex>$<hash_hex>'
        created_at      TEXT NOT NULL,
        last_login_at   TEXT,
        failed_attempts INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_auth_username
        ON auth_credentials(username COLLATE NOCASE);

    -- user_sessions: one row per "Remember Me" device token. We store the
    -- SHA-256 HASH of the token, never the raw token; the device holds the only
    -- raw copy. FK'd to the profile so deleting an account revokes every device.
    CREATE TABLE IF NOT EXISTS user_sessions (
        token_hash  TEXT PRIMARY KEY,           -- SHA-256 hex of the client token
        user_id     TEXT NOT NULL,
        created_at  TEXT NOT NULL,              -- ISO-8601 UTC
        expires_at  TEXT NOT NULL,              -- ISO-8601 UTC
        FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
    """

    # ----- credentials -----
    INSERT_CREDENTIALS = (
        "INSERT INTO auth_credentials "
        "(user_id, username, email, password_hash, created_at) "
        "VALUES (?, ?, ?, ?, ?)"
    )
    SELECT_BY_LOGIN = (
        "SELECT user_id, password_hash FROM auth_credentials "
        "WHERE username = ? OR email = ? LIMIT 1"
    )
    UPDATE_LOGIN_RESULT = (
        "UPDATE auth_credentials "
        "SET last_login_at = ?, "
        "    failed_attempts = CASE WHEN ? THEN 0 ELSE failed_attempts + 1 END "
        "WHERE user_id = ?"
    )
    EXISTS_BY_USERNAME = "SELECT 1 FROM auth_credentials WHERE username = ? LIMIT 1"
    EXISTS_BY_EMAIL    = "SELECT 1 FROM auth_credentials WHERE email = ? LIMIT 1"

    # ----- remember-me sessions -----
    INSERT_SESSION = (
        "INSERT INTO user_sessions (token_hash, user_id, created_at, expires_at) "
        "VALUES (?, ?, ?, ?)"
    )
    SELECT_SESSION = (
        "SELECT user_id, expires_at FROM user_sessions WHERE token_hash = ? LIMIT 1"
    )
    DELETE_SESSION = "DELETE FROM user_sessions WHERE token_hash = ?"
    DELETE_EXPIRED_SESSIONS = "DELETE FROM user_sessions WHERE expires_at <= ?"


# ============================================================================
#  Profile — user_profiles + user_blocks
# ============================================================================

class ProfileQueries:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS user_profiles (
        user_id        TEXT PRIMARY KEY,
        email          TEXT NOT NULL UNIQUE,
        phone          TEXT UNIQUE,
        registered_at  TEXT NOT NULL,
        status         INTEGER NOT NULL,
        gender         TEXT NOT NULL,
        date_of_birth  TEXT NOT NULL,

        -- Hebrew/RTL: stored as UTF-8 JSON to preserve gender variants verbatim.
        display_name_json  TEXT NOT NULL,
        bio_json           TEXT NOT NULL,
        looking_for_json   TEXT NOT NULL,

        location_json     TEXT NOT NULL,
        lifestyle_json    TEXT NOT NULL,
        ice_breakers_json TEXT NOT NULL DEFAULT '[]',
        photo_urls_json   TEXT NOT NULL DEFAULT '[]',
        extras_json       TEXT NOT NULL DEFAULT '{}',

        safety_flags  INTEGER NOT NULL DEFAULT 0,
        verification_level INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_user_safety_flagged
        ON user_profiles(safety_flags) WHERE safety_flags > 0;

    CREATE TABLE IF NOT EXISTS user_blocks (
        blocker_id TEXT NOT NULL,
        blocked_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (blocker_id, blocked_id),
        FOREIGN KEY (blocker_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
    );
    """

    # Full-column UPSERT (never INSERT OR REPLACE: a REPLACE would DELETE the row
    # and cascade-wipe the user's credentials/sessions/messages). ON CONFLICT
    # mutates in place. Named params bound from the serialized row dict.
    UPSERT = """
    INSERT INTO user_profiles (
        user_id, email, phone, registered_at, status, gender, date_of_birth,
        display_name_json, bio_json, looking_for_json, location_json,
        lifestyle_json, ice_breakers_json, photo_urls_json, extras_json,
        safety_flags, verification_level, updated_at
    ) VALUES (
        :user_id, :email, :phone, :registered_at, :status, :gender, :date_of_birth,
        :display_name_json, :bio_json, :looking_for_json, :location_json,
        :lifestyle_json, :ice_breakers_json, :photo_urls_json, :extras_json,
        :safety_flags, :verification_level, :updated_at
    )
    ON CONFLICT(user_id) DO UPDATE SET
        email             = excluded.email,
        phone             = excluded.phone,
        registered_at     = excluded.registered_at,
        status            = excluded.status,
        gender            = excluded.gender,
        date_of_birth     = excluded.date_of_birth,
        display_name_json = excluded.display_name_json,
        bio_json          = excluded.bio_json,
        looking_for_json  = excluded.looking_for_json,
        location_json     = excluded.location_json,
        lifestyle_json    = excluded.lifestyle_json,
        ice_breakers_json = excluded.ice_breakers_json,
        photo_urls_json   = excluded.photo_urls_json,
        extras_json       = excluded.extras_json,
        safety_flags      = excluded.safety_flags,
        verification_level= excluded.verification_level,
        updated_at        = excluded.updated_at
    """

    # Single source for the default main-picture photo list (index 0 = the
    # bundled UNDEFINED_PROFILE.png template). Used both to seed new accounts and
    # to heal old ones.
    DEFAULT_PHOTOS_JSON = json.dumps([AssetPaths.DEFAULT_PROFILE_IMAGE])

    # Backward-compat lazy migration: heal a pre-feature account whose photo list
    # is NULL / empty / '[]' / 'null' by seeding the default main picture.
    # CONDITIONAL + idempotent — a no-op on any account that already has photos,
    # so it is safe to call on every own-profile view / login.
    HEAL_MISSING_PHOTOS = (
        "UPDATE user_profiles "
        "SET photo_urls_json = ?, updated_at = ? "
        "WHERE user_id = ? "
        "  AND (photo_urls_json IS NULL "
        "       OR TRIM(photo_urls_json) IN ('', '[]', 'null'))"
    )

    SELECT_BY_ID    = "SELECT * FROM user_profiles WHERE user_id = ?"
    SELECT_BLOCKS   = "SELECT blocked_id FROM user_blocks WHERE blocker_id = ?"
    SELECT_ID_BY_EMAIL = "SELECT user_id FROM user_profiles WHERE email = ? LIMIT 1"
    DELETE          = "DELETE FROM user_profiles WHERE user_id = ?"
    UPDATE_SAFETY_FLAGS = (
        "UPDATE user_profiles SET safety_flags = ?, updated_at = ? WHERE user_id = ?"
    )
    INSERT_BLOCK = (
        "INSERT OR IGNORE INTO user_blocks (blocker_id, blocked_id, created_at) "
        "VALUES (?, ?, ?)"
    )

    DISCOVER = (
        "SELECT * FROM user_profiles "
        "WHERE user_id != ? "
        "  AND status IN (?, ?) "
        "  AND user_id NOT IN ("
        "        SELECT blocked_id FROM user_blocks WHERE blocker_id = ?"
        "  ) "
        "ORDER BY datetime(registered_at) DESC "
        "LIMIT ?"
    )

    # Minimal NOT-NULL profile written at signup so auth + DM FKs are satisfied;
    # full fields land later via save_profile() during onboarding. (Executed by
    # SqliteAuthService inside the signup transaction — the profile SQL stays in
    # the profile ledger, the auth service merely orchestrates.)
    INSERT_MINIMAL_PROFILE = """
    INSERT OR IGNORE INTO user_profiles
        (user_id, email, registered_at, status, gender, date_of_birth,
         display_name_json, bio_json, looking_for_json,
         location_json, lifestyle_json, photo_urls_json, updated_at)
    VALUES
        (:user_id, :email, :registered_at, :status, :gender, :date_of_birth,
         :display_name_json, :bio_json, :looking_for_json,
         :location_json, :lifestyle_json, :photo_urls_json, :updated_at)
    """

    @staticmethod
    def minimal_profile_params(
        user_id: str, username: str, email: str, now_iso: str,
    ) -> dict:
        """Build the bound params for INSERT_MINIMAL_PROFILE. Hebrew-safe JSON
        (`ensure_ascii=False`); the username seeds all three gender variants."""
        username_lt = json.dumps(
            {"he_male": username, "he_female": username, "he_neutral": username},
            ensure_ascii=False,
        )
        return {
            "user_id":           user_id,
            "email":             email,
            "registered_at":     now_iso,
            "status":            AccountStatus.PENDING.value,
            "gender":            Gender.OTHER.value,
            "date_of_birth":     "1900-01-01",   # sentinel; replaced at onboarding
            "display_name_json": username_lt,
            "bio_json":          username_lt,
            "looking_for_json":  username_lt,
            "location_json":     json.dumps(
                {"city": "", "region": None, "lat": None, "lon": None,
                 "visibility_radius_km": 50}),
            "lifestyle_json":    json.dumps({}),
            # Seed the MAIN profile picture (index 0) with the default template
            # at registration. A user's main picture is therefore never null.
            "photo_urls_json":   ProfileQueries.DEFAULT_PHOTOS_JSON,
            "updated_at":        now_iso,
        }


# ============================================================================
#  Messaging — direct_messages
# ============================================================================

class MessagingQueries:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS direct_messages (
        message_id      TEXT PRIMARY KEY,           -- UUID4
        conversation_id TEXT NOT NULL,              -- 'min_uid|max_uid'
        sender_id       TEXT NOT NULL,
        recipient_id    TEXT NOT NULL,
        content         TEXT NOT NULL,              -- text body OR storage URL
        msg_type        INTEGER NOT NULL,           -- MessageType.value
        status          INTEGER NOT NULL DEFAULT 1, -- MessageStatus.SENT
        created_at      TEXT NOT NULL,              -- ISO-8601 UTC
        delivered_at    TEXT,
        read_at         TEXT,
        FOREIGN KEY (sender_id)    REFERENCES user_profiles(user_id) ON DELETE CASCADE,
        FOREIGN KEY (recipient_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
        CHECK (sender_id <> recipient_id)
    );
    CREATE INDEX IF NOT EXISTS idx_dm_conv_time
        ON direct_messages (conversation_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_dm_unread
        ON direct_messages (recipient_id, status, sender_id);
    CREATE INDEX IF NOT EXISTS idx_dm_endpoints
        ON direct_messages (sender_id, recipient_id, created_at);
    """

    INSERT_MESSAGE = (
        "INSERT INTO direct_messages "
        "(message_id, conversation_id, sender_id, recipient_id, "
        " content, msg_type, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )
    # Cursor-based history (no OFFSET — keeps the contract portable to a NoSQL
    # `startAfter` cursor). Both variants page NEWEST-FIRST (the service reverses
    # the slice for top-down rendering) and lean on idx_dm_conv_time
    # (conversation_id, created_at DESC) so paging stays O(limit), never O(offset).
    #
    # _LATEST: the first page — newest `limit` messages, no cursor yet.
    SELECT_HISTORY_LATEST = (
        "SELECT message_id, conversation_id, sender_id, recipient_id, "
        "       content, msg_type, status, created_at, delivered_at, read_at "
        "FROM direct_messages "
        "WHERE conversation_id = ? "
        "ORDER BY created_at DESC, message_id DESC "
        "LIMIT ?"
    )
    # _BEFORE: subsequent pages — the `limit` messages strictly OLDER than the
    # caller's cursor (the `created_at` of the oldest message already on screen).
    SELECT_HISTORY_BEFORE = (
        "SELECT message_id, conversation_id, sender_id, recipient_id, "
        "       content, msg_type, status, created_at, delivered_at, read_at "
        "FROM direct_messages "
        "WHERE conversation_id = ? AND created_at < ? "
        "ORDER BY created_at DESC, message_id DESC "
        "LIMIT ?"
    )
    MARK_READ = (
        "UPDATE direct_messages "
        "SET status = ?, read_at = ? "
        "WHERE recipient_id = ? AND sender_id = ? AND status < ?"
    )
    UNREAD_COUNTS = (
        "SELECT sender_id, COUNT(*) AS cnt "
        "FROM direct_messages "
        "WHERE recipient_id = ? AND status < ? "
        "GROUP BY sender_id"
    )
    CONVERSATIONS = (
        "SELECT m.sender_id, m.recipient_id, m.content, m.msg_type, m.created_at "
        "FROM direct_messages m "
        "JOIN ( "
        "    SELECT conversation_id, MAX(created_at) AS max_at "
        "    FROM direct_messages "
        "    WHERE sender_id = ? OR recipient_id = ? "
        "    GROUP BY conversation_id "
        ") latest "
        "  ON m.conversation_id = latest.conversation_id "
        " AND m.created_at = latest.max_at "
        "WHERE m.sender_id = ? OR m.recipient_id = ? "
        "ORDER BY m.created_at DESC, m.message_id DESC"
    )
