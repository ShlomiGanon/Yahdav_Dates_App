"""Shared session-store helpers used across views."""
from __future__ import annotations

import flet as ft


def safe_remove(page: ft.Page, *keys: str) -> None:
    """Remove session-store keys if present.

    Flet's `SessionStore.remove` delegates to `dict.pop` and raises KeyError on
    missing keys, which is too noisy for defensive cleanup paths (logout, login
    pre-flight). This wrapper makes the operation idempotent — a missing key is
    simply skipped.
    """
    store = page.session.store
    for k in keys:
        if store.contains_key(k):
            store.remove(k)
