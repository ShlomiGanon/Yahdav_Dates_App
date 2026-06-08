"""Read-only profile field row — a label over its value, used by the peer
profile screen. Centralised so the label/value typography and the RTL recipe
live in one place."""
import flet as ft

from style.design_system import DS


def create_profile_field(label: str, value: str) -> ft.Control:
    """A read-only label/value block. STRETCH + RIGHT text_align (never END —
    the RTL trap). The value Text wraps within the bounded card width, so even a
    very long bio stays inside the layout boundary (no black-screen overflow)."""
    return ft.Column(
        controls=[
            ft.Text(
                label,
                size=DS.type.body,
                weight=ft.FontWeight.W_600,
                color=DS.palette.secondary,
                rtl=True,
                text_align=ft.TextAlign.RIGHT,
            ),
            ft.Text(
                value,
                size=DS.type.input,
                color=DS.palette.text_main,
                rtl=True,
                text_align=ft.TextAlign.RIGHT,
                selectable=True,
                # Wrap (default) within the card; clip the rare unbroken
                # mega-token so it can't blow out the layout width.
                overflow=ft.TextOverflow.CLIP,
            ),
        ],
        spacing=DS.spacing.xxs,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
