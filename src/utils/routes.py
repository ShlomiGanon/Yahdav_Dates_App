"""Canonical route-path constants — the single source of truth for every
screen's URL string. The router maps each one to its view factory; every
view (and `views.common.helpers.navigation`) imports from here to navigate, declare
its own `ROUTE`, or name the screens it can land on — so a path never has to
be retyped (and risk drifting) at a second call site."""
from __future__ import annotations

WELCOME = "/auth/welcome"
LOGIN = "/auth/login"
SIGNUP = "/auth/signup"
MENU = "/menu"
MY_PROFILE = "/profile/me"
ADDITIONAL_PHOTOS = "/profile/photos"
DISCOVER = "/matching/discover"
PEER_PROFILE = "/discover/profile"
PEER_PHOTOS = "/discover/peer_photos"
CHAT_HISTORY = "/chat/history"
CHAT_NEW = "/chat/new"
