from __future__ import annotations
from abc import ABC, abstractmethod

from models.user_profile import UserProfile, SafetyFlag


class IProfileRepository(ABC):
    """CRUD over the `UserProfile` aggregate.

    Storage-agnostic: implementations may use SQLite, Firestore, or anything
    else. The UI layer (onboarding, profile, public-profile views) depends
    only on this interface.
    """

    @abstractmethod
    def get_profile(self, user_id: str) -> UserProfile | None:
        """Return the profile, or None if no row exists."""
        pass

    @abstractmethod
    def save_profile(self, profile: UserProfile) -> None:
        """Insert-or-update (UPSERT) the profile in place — never a destructive
        INSERT OR REPLACE, which would cascade-delete the user's credentials and
        sessions. Raises ValueError on uniqueness violations (duplicate
        email/phone)."""
        pass

    @abstractmethod
    def find_profile_by_email(self, email: str) -> UserProfile | None:
        pass

    @abstractmethod
    def discover_profiles(self, viewer_id: str, limit: int) -> list[UserProfile]:
        """Return candidate profiles for `viewer_id`'s discover feed.

        Contract every implementation must honour:
          • EXCLUDE the viewer themselves.
          • EXCLUDE anyone the viewer has blocked.
          • EXCLUDE accounts not eligible to be shown (suspended / deleted).
          • Order newest-registered first; cap the result at `limit`.

        Read path: returns an empty list (never raises) on any storage error,
        so the discover view degrades to an empty-state banner rather than a
        crash. `limit` is clamped by the implementation to a sane ceiling.
        """
        pass

    @abstractmethod
    def delete_profile(self, user_id: str) -> None:
        """Cascade-delete the profile and everything FK'd to it
        (auth row, blocks, messages)."""
        pass

    @abstractmethod
    def update_safety_flags(self, user_id: str, flags: SafetyFlag) -> None:
        """Replace the safety-flag bitfield. Used by moderation flows."""
        pass

    @abstractmethod
    def add_block(self, blocker_id: str, blocked_id: str) -> None:
        pass

    @abstractmethod
    def ensure_default_photo(self, user_id: str) -> None:
        """Backward-compat lazy migration: if this account has no stored main
        picture (a pre-feature row with a null/empty photo list), persist the
        default `UNDEFINED_PROFILE.png` template so the record is permanently
        healed. MUST be idempotent and best-effort — a no-op on accounts that
        already have photos, and it never raises (a heal failure must not break
        login or profile viewing). Called off the UI thread."""
        pass
