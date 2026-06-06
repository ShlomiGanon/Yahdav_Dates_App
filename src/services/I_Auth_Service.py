from abc import ABC, abstractmethod


class IAuthService(ABC):
    """Identity & credentials. Owns signup, login, and input validation.

    Knows nothing about profile fields, messaging, or storage details.
    """

    # ----- Account lifecycle -----

    @abstractmethod
    def signup_user(self, username: str, email: str, password: str) -> bool:
        """Create a new account. Returns False if validation fails or the
        username/email is taken."""
        pass

    @abstractmethod
    def login_user(self, username_or_email: str, password: str) -> str | None:
        """Verify credentials and identify the user.

        Returns:
            The authenticated user's UID (string) on success, or `None` on
            bad password / unknown user / any infra error (errors are logged,
            never raised to the UI).

        Why a UID, not a bool: login produces an identity. Returning only
        True/False forced callers to issue a second lookup just to know who
        had logged in. Returning the UID lets the view stash it on
        `page.session.store` and route to user-scoped screens immediately.
        """
        pass

    # ----- "Remember Me" — long-lived device tokens -----

    @abstractmethod
    def generate_remember_me_token(self, user_id: str) -> str:
        """Mint a long-lived session token for "stay signed in on this device".

        Generates a cryptographically-secure random token, persists a HASH of
        it (never the raw token) against `user_id` with an expiry derived from
        `AuthConfig.REMEMBER_ME_DAYS`, and returns the RAW token for the caller
        to persist on the device (via the `utils.local_storage` seam — a small,
        fsync'd JSON file alongside the SQLite DB).

        The raw token lives only on the device; the server keeps just its hash,
        so a database leak cannot be replayed as a login.
        """
        pass

    @abstractmethod
    def validate_remember_me_token(self, token: str) -> str | None:
        """Resolve a remember-me token back to its owner.

        Returns:
            The `user_id` if the token exists and has not expired, else `None`.
            Expired/unknown tokens never raise — a bad token simply means
            "log in again". Implementations should purge an expired row on hit.
        """
        pass

    @abstractmethod
    def revoke_remember_me_token(self, token: str) -> None:
        """Invalidate a remember-me token server-side (explicit logout).

        Hashes the raw token the same way `generate_remember_me_token` did and
        deletes the matching `user_sessions` row, so the token can never again
        auto-login — even if a stale copy lingers on some device. Revoking a
        missing/empty token is a no-op (idempotent). Used by the logout flow,
        wrapped in `asyncio.to_thread` since it touches the DB.
        """
        pass

    # ----- Existence probes (signup-time UX hints) -----

    @abstractmethod
    def is_username_exists(self, username: str) -> bool:
        pass

    @abstractmethod
    def is_email_exists(self, email: str) -> bool:
        pass

    # ----- Static validators (no I/O — pure functions) -----

    @staticmethod
    @abstractmethod
    def is_email_valid(email: str) -> bool:
        pass

    @staticmethod
    @abstractmethod
    def is_username_valid(username: str) -> bool:
        pass

    @staticmethod
    @abstractmethod
    def is_password_valid(password: str) -> bool:
        pass
