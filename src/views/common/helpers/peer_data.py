"""Shared, defensive accessors for untrusted peer `UserProfile` data — the
reusable form of the Peer Layout Boundary Rule's "never raise" guarantee.

`UserProfileView` and `PeerPhotosView` both render someone ELSE's
partially-populated profile, so both need the same "read this field, or
degrade to a safe default" recipe. Centralising it here means a null
localization, a missing value object, or an empty photo array degrades
identically wherever a peer's data is shown — and a future peer-facing
screen gets the same guarantees for free.
"""
from __future__ import annotations

from models.user_profile import UserProfile, GENDER_LABELS_HE
from utils.constants import AssetPaths


def safe_str(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def safe_display_name(profile: UserProfile) -> str:
    """The gendered display name, stripped — or `""` if missing/unreadable.

    Returns `""` rather than a fallback label so each screen can choose its
    OWN empty-name behaviour (e.g. PeerPhotosView shows a generic album
    heading instead of "album of <fallback>"; UserProfileView always needs a
    non-empty label and applies its own fallback on top of this)."""
    try:
        return safe_str(profile.display_name.for_gender(profile.gender))
    except Exception:  # noqa: BLE001
        return ""


def safe_bio(profile: UserProfile) -> str:
    try:
        return safe_str(profile.bio.for_gender(profile.gender))
    except Exception:  # noqa: BLE001
        return ""


def safe_gender_label(profile: UserProfile) -> str | None:
    try:
        return GENDER_LABELS_HE.get(profile.gender)
    except Exception:  # noqa: BLE001
        return None


def safe_age(profile: UserProfile) -> str | None:
    try:
        dob = profile.date_of_birth
        if dob and dob.year > 1900:          # skip the un-onboarded sentinel
            return str(profile.age)
    except Exception:  # noqa: BLE001
        pass
    return None


def safe_dob(profile: UserProfile) -> str | None:
    try:
        dob = profile.date_of_birth
        if dob and dob.year > 1900:
            return dob.strftime("%d/%m/%Y")
    except Exception:  # noqa: BLE001
        pass
    return None


def safe_location(profile: UserProfile) -> str:
    try:
        loc = profile.location
        parts = [p for p in (
            (loc.city or "").strip(), (loc.region or "").strip(),
        ) if p]
        return ", ".join(parts)
    except Exception:  # noqa: BLE001
        return ""


def safe_src(src: object) -> str:
    """Resolve a single picture src, degrading any unusable value to the
    bundled default template (`AssetPaths.DEFAULT_PROFILE_IMAGE`)."""
    if isinstance(src, str) and src.strip():
        return src.strip()
    return AssetPaths.DEFAULT_PROFILE_IMAGE


def safe_photo_src(profile: UserProfile) -> str:
    """Resolve the MAIN picture src with an EXPLICIT length guard — never
    assume the photo list coming from the DB is populated. If it's missing,
    empty, or position 0 isn't a usable string, force the default template."""
    try:
        photos = profile.photo_urls
        if photos and len(photos) >= 1 and isinstance(photos[0], str) and photos[0].strip():
            return photos[0]
    except Exception:  # noqa: BLE001 — any access issue → default
        pass
    return AssetPaths.DEFAULT_PROFILE_IMAGE
