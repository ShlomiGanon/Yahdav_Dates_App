"""Shared in-shell error card — a styled, RTL danger-tinted card with an icon, a
message and a calm recovery hint. Used by the read-only peer screens (peer profile
+ album) when a load/render fails, so the failure UI is identical in one place
instead of hand-rolled per screen. All styling comes from the Design System."""
import flet as ft

from style.design_system import DS


def create_error_card(
    message: str,
    *,
    hint: str = "אפשר לחזור ולנסות שוב.",
) -> ft.Container:
    """A styled, RTL error card shown inside the translucent shell."""
    return ft.Container(
        bgcolor=ft.Colors.with_opacity(DS.opacity.error_card, DS.palette.danger),
        border_radius=DS.radius.card,
        padding=DS.pad.section,
        content=ft.Column(
            controls=[
                ft.Icon(ft.Icons.ERROR_OUTLINE, size=DS.sizing.icon_lg,
                        color=DS.palette.danger),
                ft.Text(
                    message, size=DS.type.input, weight=ft.FontWeight.W_600,
                    color=DS.palette.text_main, rtl=True,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    hint, size=DS.type.body,
                    color=DS.palette.text_main, rtl=True,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            tight=True,
            spacing=DS.spacing.md,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
