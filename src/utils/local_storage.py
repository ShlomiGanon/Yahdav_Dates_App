"""Device-local "Remember Me" token storage — Flet `page.shared_preferences`.

The device persists ONLY the raw, opaque token string (under
`AuthConfig.REMEMBER_ME_CLIENT_KEY`). The authoritative session state — the
SHA-256 token hash plus `user_id` / `created_at` / `expires_at`, and all validity
and cleanup logic — lives in the `user_sessions` table owned by
`SqliteAuthService`. There is NO JSON file.

`page.shared_preferences` reads are async client round-trips. `read_token`
awaits that round-trip directly, so `Router.resolve_initial_route` settles on
the result the instant the client store resolves (no fixed boot delay). Every
call here is defensive — a storage hiccup degrades to "no token" rather than
crashing boot.
"""
from __future__ import annotations
import logging

import flet as ft

from utils.constants import AuthConfig

log = logging.getLogger(__name__)

# Single source for the device-storage key (mirrors AuthConfig).
_KEY: str = AuthConfig.REMEMBER_ME_CLIENT_KEY


async def write_token(page: ft.Page, token: str) -> bool:
    """Persist the raw remember-me token on the device. Returns False if the
    token is empty or the client store rejected the write."""
    if not token:
        return False
    try:
        ok = await page.shared_preferences.set(_KEY, token)
        log.info("remember-me: token persisted=%s", bool(ok))
        return bool(ok)
    except Exception:  # noqa: BLE001 — never let a storage hiccup crash the flow
        log.warning("remember-me: write_token failed", exc_info=True)
        return False


async def read_token(page: ft.Page) -> str | None:
    """Return the stored raw token, or None if absent/unreadable."""
    try:
        value = await page.shared_preferences.get(_KEY)
    except Exception:  # noqa: BLE001
        log.warning("remember-me: read_token failed", exc_info=True)
        return None
    return value if isinstance(value, str) and value else None


async def clear_token(page: ft.Page) -> None:
    """Remove the device token. Idempotent — a missing key is success."""
    try:
        await page.shared_preferences.remove(_KEY)
        log.info("remember-me: token cleared")
    except Exception:  # noqa: BLE001
        log.warning("remember-me: clear_token failed", exc_info=True)
