"""Shared navigation helpers for internal screens."""
from __future__ import annotations

import flet as ft

from components.buttons import create_secondary_button
from utils.routes import MENU

# Canonical Main Menu route. Alias of `utils.routes.MENU` (mirrors
# MainMenuView.ROUTE) so this lightweight helper module need not import a
# whole view class.
MENU_ROUTE = MENU


def back_to_menu_button(page: ft.Page) -> ft.Button:
    """A senior-friendly 'Return to Main Menu' button for any internal screen.

    Secondary (blue-grey) styling so it reads as navigation, distinct from the
    primary content action on the screen. Simply routes to the Main Menu.
    """
    return create_secondary_button(
        "חזור לתפריט הראשי",
        lambda _e: page.go(MENU_ROUTE),
    )


def go_back(page: ft.Page, *, fallback: str = MENU_ROUTE) -> None:
    """Stack-aware 'go back one screen'.

    Pops to the view immediately BELOW the top of `page.views` by navigating to
    its route. The router turns a `page.go(...)` to a route already present in
    the stack into an UNWIND, so the parent view is revealed with its state
    intact (scroll position, loaded data) rather than rebuilt.

    This is the right call whenever the user expects "back one screen" but the
    current screen can be opened from MORE THAN ONE place (e.g. ChatView is
    reached from both Discover and Matches) — hard-coding a single parent route
    would send the user to the wrong screen. When the stack holds only the root
    view (depth ≤ 1) there is nothing to pop to, so it routes to `fallback`
    (the Main Menu by default) — a safe landing instead of a dead end.

    Fully guarded: a back action must never raise into the event loop.
    """
    try:
        views = getattr(page, "views", None) or []
        if len(views) > 1:
            parent_route = getattr(views[-2], "route", None)
            if parent_route:
                page.go(parent_route)
                return
    except Exception:  # noqa: BLE001 — back navigation must never crash
        pass
    page.go(fallback)


def back_button(
    page: ft.Page,
    *,
    label: str = "חזור",
    fallback: str = MENU_ROUTE,
) -> ft.Button:
    """A senior-friendly, SECONDARY (blue-grey) stack-aware back button.

    Routes through `go_back`, so it returns to whichever screen actually opened
    the current one — never a hard-coded parent. Use this instead of
    `page.go(HARDCODED_PARENT)` for any "back one screen" affordance.
    """
    return create_secondary_button(
        label, lambda _e: go_back(page, fallback=fallback),
    )
