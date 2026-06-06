"""Shared navigation helpers for internal screens."""
from __future__ import annotations

import flet as ft

from components.buttons import create_secondary_button

# Canonical Main Menu route. Kept as a literal here (mirrors MainMenuView.ROUTE)
# so this lightweight helper module need not import a whole view class.
MENU_ROUTE = "/menu"


def back_to_menu_button(page: ft.Page) -> ft.Button:
    """A senior-friendly 'Return to Main Menu' button for any internal screen.

    Secondary (blue-grey) styling so it reads as navigation, distinct from the
    primary content action on the screen. Simply routes to the Main Menu.
    """
    return create_secondary_button(
        "חזור לתפריט הראשי",
        lambda _e: page.go(MENU_ROUTE),
    )
