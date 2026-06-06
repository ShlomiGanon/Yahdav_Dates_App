"""Shared screen-layout helpers — the single source of the app's full-screen
background + translucent-card visual language.

Centralising these means every screen (Main Menu, My Profile, placeholders…)
shares one definition of the background treatment and the form/card overlay, so
the look can be tuned in exactly one place. All concrete values come from
`utils.constants` (`AssetPaths.BG_IMAGE`, `UIConstants.FORM_OVERLAY_OPACITY`,
`CORNER_RADIUS`, `CARD_PADDING`).
"""
from __future__ import annotations

import flet as ft

from utils.constants import AssetPaths, UIConstants, ThemeColors


def background_screen(route: str, content: ft.Control) -> ft.View:
    """A full-screen `ft.View` with the shared 'BG' image behind `content`.

    The full-bleed background is achieved by three cooperating settings:
      • `expand=True` on the image container fills the available HEIGHT,
      • `CrossAxisAlignment.STRETCH` on the View fills the WIDTH, and
      • `BoxFit.FILL` shows the WHOLE artwork edge-to-edge (no crop; the image
        stretches/compresses to the window, aspect ratio not preserved).
    `content` is laid directly on top, filling the same box.
    """
    return ft.View(
        route=route,
        padding=0,
        vertical_alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ft.Container(
                expand=True,
                # Solid colour BEHIND the image. If `BG.png` fails to resolve or
                # is still loading mid-navigation, the container paints this
                # instead of falling through to an unset page background — which
                # the Flet desktop client renders BLACK. This single line is the
                # structural guard against the "completely black screen".
                bgcolor=ThemeColors.BACKGROUND,
                image=ft.DecorationImage(
                    src=AssetPaths.BG_IMAGE,
                    fit=ft.BoxFit.FILL,
                ),
                content=content,
            ),
        ],
    )


def translucent_card(
    content: ft.Control,
    *,
    expand: bool = False,
    margin: ft.Margin | None = None,
    padding: ft.Padding | int | None = None,
) -> ft.Container:
    """A semi-transparent white card so `content` stays readable over the BG.

    Uses `UIConstants.FORM_OVERLAY_OPACITY` (white at 50%) and the standard
    corner radius, so the background image shows through while text stays
    legible — identical to the My Profile form card.
    """
    return ft.Container(
        content=content,
        expand=expand,
        margin=margin,
        padding=UIConstants.CARD_PADDING if padding is None else padding,
        bgcolor=ft.Colors.with_opacity(
            UIConstants.FORM_OVERLAY_OPACITY, ThemeColors.SURFACE,
        ),
        border_radius=UIConstants.CORNER_RADIUS,
    )
