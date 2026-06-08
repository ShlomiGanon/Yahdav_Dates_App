"""Canonical session-store key strings, shared by the router and every
view that reads or writes `page.session.store`."""
from __future__ import annotations

CURRENT_USER_ID = "current_user_id"
CURRENT_USER_EMAIL = "current_user_email"
SELECTED_PEER_ID = "selected_peer_id"
