import flet as ft

from views.common.screen import background_screen, translucent_card
from utils.constants import UIConstants


def auth_modal(page: ft.Page, route: str, card_content: ft.Control) -> ft.View:
    """Shared auth-screen frame — the SAME shell as every other screen.

    Login and Signup used to render a bespoke modal (a raw dark scrim + a custom
    white card with a hand-rolled shadow), which made them the only screens that
    didn't share the app-wide look. This now derives from the centralized shell:
    the full-screen `background_screen` (BG image + black-screen guard) with the
    content in a 50%-white `translucent_card`, centered — identical to the Main
    Menu / Welcome / Placeholder screens. Dismissal is the card's own "ביטול"
    button (which routes to /auth/welcome); the previous tap-the-backdrop gesture
    is no longer needed, so `page` is unused but kept for signature stability.
    """
    card = translucent_card(card_content, padding=UIConstants.CARD_PADDING)
    centered = ft.Column(
        controls=[card],
        expand=True,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return background_screen(route, centered)
