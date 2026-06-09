"""SqliteMessagingService — concrete IMessagingService over SQLite.

Owns the direct_messages table. Isolated from the other services — shares only
`db_path`. All SQL comes from `sqlite_queries`; row→dict parsing is centralized
in `_row_to_message_dict`.
"""
from __future__ import annotations
import logging
import sqlite3
import uuid
from contextlib import AbstractContextManager
from datetime import datetime, timezone

from services.interfaces.i_messaging_service import IMessagingService
from services.sqlite.sqlite_queries import connection, MessagingQueries
from utils.constants import ChatConfig, MessageType, MessageStatus

log = logging.getLogger(__name__)


class SqliteMessagingService(IMessagingService):
    """One-on-one direct messaging, backed by SQLite."""

    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self._initialize()

    def _initialize(self) -> None:
        """Create direct_messages. The profile repository must be initialized
        first (sender_id/recipient_id FK user_profiles)."""
        try:
            with self._conn() as c:
                c.executescript(MessagingQueries.SCHEMA)
        except sqlite3.Error as e:
            log.exception("messaging schema init failed: %s", e)
            raise RuntimeError("messaging backend init failed") from e

    # ---- Thread-safe connection seam (delegate to the ledger) ----
    def _conn(self) -> AbstractContextManager[sqlite3.Connection]:
        return connection(self._db_path)

    # ============================================================
    #  Helpers
    # ============================================================

    @staticmethod
    def _conversation_key(user_a: str, user_b: str) -> str:
        """Deterministic key shared by both directions of a chat."""
        lo, hi = (user_a, user_b) if user_a < user_b else (user_b, user_a)
        return f"{lo}{ChatConfig.CONVERSATION_SEPARATOR}{hi}"

    @staticmethod
    def _row_to_message_dict(row: sqlite3.Row) -> dict:
        """Map a direct_messages row to the wire-format dict the UI consumes."""
        return {
            "message_id":      row["message_id"],
            "conversation_id": row["conversation_id"],
            "sender_id":       row["sender_id"],
            "recipient_id":    row["recipient_id"],
            "content":         row["content"],
            "msg_type":        MessageType(row["msg_type"]).name,
            "status":          MessageStatus(row["status"]).name,
            "created_at":      row["created_at"],
            "delivered_at":    row["delivered_at"],
            "read_at":         row["read_at"],
        }

    # ============================================================
    #  IMessagingService
    # ============================================================

    def send_direct_message(
        self,
        sender_id: str,
        recipient_id: str,
        content: str,
        msg_type: MessageType,
    ) -> str:
        if not sender_id or not recipient_id:
            raise ValueError("sender_id and recipient_id are required")
        if sender_id == recipient_id:
            raise ValueError("cannot send a message to yourself")
        if not isinstance(msg_type, MessageType):
            raise TypeError(f"msg_type must be MessageType, got {type(msg_type).__name__}")
        if not content:
            raise ValueError("content must not be empty")
        if msg_type is MessageType.TEXT and len(content) > ChatConfig.MAX_TEXT_LENGTH:
            raise ValueError(f"text exceeds MAX_TEXT_LENGTH ({ChatConfig.MAX_TEXT_LENGTH})")

        message_id = str(uuid.uuid4())
        conversation_id = self._conversation_key(sender_id, recipient_id)
        created_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        try:
            with self._conn() as c:
                c.execute(
                    MessagingQueries.INSERT_MESSAGE,
                    (message_id, conversation_id, sender_id, recipient_id,
                     content, msg_type.value, MessageStatus.SENT.value, created_at),
                )
            log.debug("dm sent id=%s from=%s to=%s type=%s",
                      message_id, sender_id, recipient_id, msg_type.name)
            return message_id
        except sqlite3.IntegrityError as e:
            log.warning("dm rejected (integrity) from=%s to=%s: %s",
                        sender_id, recipient_id, e)
            raise ValueError("sender_id or recipient_id does not exist") from e
        except sqlite3.Error as e:
            log.exception("dm send failed from=%s to=%s: %s", sender_id, recipient_id, e)
            raise RuntimeError("failed to send direct message") from e

    def get_chat_history(
        self,
        user_a: str,
        user_b: str,
        limit: int,
        cursor_timestamp: str | None = None,
    ) -> list[dict]:
        if not user_a or not user_b:
            raise ValueError("user_a and user_b are required")
        safe_limit = max(1, min(int(limit), ChatConfig.MAX_PAGE_SIZE))
        conversation_id = self._conversation_key(user_a, user_b)

        # Cursor-based paging: no cursor ⇒ newest page; a cursor ⇒ the page of
        # messages strictly older than it. Both queries fetch newest-first.
        if cursor_timestamp:
            query = MessagingQueries.SELECT_HISTORY_BEFORE
            params = (conversation_id, cursor_timestamp, safe_limit)
        else:
            query = MessagingQueries.SELECT_HISTORY_LATEST
            params = (conversation_id, safe_limit)
        try:
            with self._conn() as c:
                rows = c.execute(query, params).fetchall()
        except sqlite3.Error as e:
            log.exception("chat history failed conv=%s: %s", conversation_id, e)
            raise RuntimeError("failed to fetch chat history") from e
        # Newest-first from SQL; reversed for chronological top-down rendering.
        return [self._row_to_message_dict(r) for r in reversed(rows)]

    def mark_messages_as_read(self, chat_owner_id: str, sender_id: str) -> None:
        if not chat_owner_id or not sender_id:
            raise ValueError("chat_owner_id and sender_id are required")
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        try:
            with self._conn() as c:
                cur = c.execute(
                    MessagingQueries.MARK_READ,
                    (MessageStatus.READ.value, now,
                     chat_owner_id, sender_id, MessageStatus.READ.value),
                )
                log.debug("marked %d msgs as read owner=%s from=%s",
                          cur.rowcount, chat_owner_id, sender_id)
        except sqlite3.Error as e:
            log.exception("mark_messages_as_read failed owner=%s from=%s: %s",
                          chat_owner_id, sender_id, e)
            raise RuntimeError("failed to mark messages as read") from e

    def get_unread_counts(self, user_id: str) -> dict[str, int]:
        if not user_id:
            raise ValueError("user_id is required")
        try:
            with self._conn() as c:
                rows = c.execute(
                    MessagingQueries.UNREAD_COUNTS,
                    (user_id, MessageStatus.READ.value),
                ).fetchall()
            return {r["sender_id"]: int(r["cnt"]) for r in rows}
        except sqlite3.Error as e:
            log.exception("get_unread_counts failed user=%s: %s", user_id, e)
            raise RuntimeError("failed to fetch unread counts") from e

    def get_conversations(self, user_id: str) -> list[dict]:
        if not user_id:
            raise ValueError("user_id is required")
        try:
            with self._conn() as c:
                rows = c.execute(
                    MessagingQueries.CONVERSATIONS,
                    (user_id, user_id, user_id, user_id),
                ).fetchall()
        except sqlite3.Error as e:
            log.exception("get_conversations failed user=%s: %s", user_id, e)
            raise RuntimeError("failed to fetch conversations") from e

        threads: list[dict] = []
        seen: set[str] = set()
        for r in rows:
            peer = r["recipient_id"] if r["sender_id"] == user_id else r["sender_id"]
            if peer in seen:
                continue
            seen.add(peer)
            threads.append({
                "peer_id":        peer,
                "last_content":   r["content"],
                "last_msg_type":  MessageType(r["msg_type"]).name,
                "last_sender_id": r["sender_id"],
                "last_at":        r["created_at"],
            })
        return threads
