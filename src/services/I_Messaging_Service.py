from abc import ABC, abstractmethod

from utils.constants import MessageType


class IMessagingService(ABC):
    """Direct messaging between two users.

    A view that opens a chat needs ONLY this interface — no auth, no profile
    storage, no SQLite. A future swap to a real-time provider (Firestore,
    WebSocket) replaces this implementation without touching `chat_view.py`.
    """

    @abstractmethod
    def send_direct_message(
        self,
        sender_id: str,
        recipient_id: str,
        content: str,
        msg_type: MessageType,
    ) -> str:
        """Persist a new direct message.

        Args:
            sender_id:    UID of the sender.
            recipient_id: UID of the recipient.
            content:      For TEXT — the text body.
                          For AUDIO/IMAGE — the storage URL or path.
            msg_type:     One of MessageType.

        Returns:
            The newly-generated message UUID (string).
        """
        pass

    @abstractmethod
    def get_chat_history(
        self,
        user_a: str,
        user_b: str,
        limit: int,
        cursor_timestamp: str | None = None,
    ) -> list[dict]:
        """Return a CURSOR-paginated slice of the conversation between two users.

        Cursor — not offset — so the contract maps cleanly onto a future NoSQL
        backend (Firestore `startAfter`), where `offset` is expensive and grows
        linearly with the page index.

        Args:
            user_a, user_b:   the two participants (order-independent).
            limit:            max messages to return (implementation clamps it).
            cursor_timestamp: ISO-8601 `created_at` of the OLDEST message already
                              loaded. `None` (default) ⇒ the newest page. To page
                              BACKWARD into history, pass the `created_at` of the
                              first (top-most) message currently on screen; the
                              call returns the `limit` messages strictly older
                              than it.

        The returned list is sorted chronologically (oldest → newest) so the UI
        renders a chat-bubble column top-down without re-sorting.
        """
        pass

    @abstractmethod
    def mark_messages_as_read(self, chat_owner_id: str, sender_id: str) -> None:
        """Mark every message FROM `sender_id` TO `chat_owner_id` as READ.
        Monotonic: SENT/DELIVERED → READ. Already-read messages untouched."""
        pass

    @abstractmethod
    def get_unread_counts(self, user_id: str) -> dict[str, int]:
        """Return badge counts for the chat list, keyed by sender UID."""
        pass

    @abstractmethod
    def get_conversations(self, user_id: str) -> list[dict]:
        """List the user's conversation threads, newest activity first.

        One dict per peer the user has exchanged messages with — powers the
        chat-history / matches screen::

            {
              "peer_id":        str,   # the OTHER participant's UID
              "last_content":   str,   # latest message body / storage URL
              "last_msg_type":  str,   # MessageType .name (TEXT / AUDIO / IMAGE)
              "last_sender_id": str,   # who sent the latest message
              "last_at":        str,   # ISO-8601 UTC of the latest message
            }

        Unread badge counts come separately from `get_unread_counts`.
        """
        pass
