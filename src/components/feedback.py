"""Inline status banner (success / error feedback above the action bar).

Form validation errors use `ft.TextField.error_text` / `error_style` directly —
no separate error-label controls needed. This module owns only the banner that
lives in the card tail between the form and the action buttons.
"""
import asyncio

import flet as ft

from style.design_system import DS


# ----------------------------------------------------------------------------
# Inline status banner (success / error feedback above the action bar)
# ----------------------------------------------------------------------------


def create_status_banner(*, width: float | None = None) -> tuple[ft.Container, ft.Text]:
    """Build the inline status banner and return `(container, text)`.

    The container starts hidden; `show_status` toggles its visibility and colour
    (SUCCESS green / DANGER red). Reliable across Flet versions — no dependency
    on `page.snack_bar`. Pass `width` to pin it (e.g. `DS.sizing.input_w`);
    omit for a full-width banner.
    """
    text = ft.Text(
        value="",
        size=DS.type.input,
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.W_600,
        rtl=True,
        text_align=ft.TextAlign.RIGHT,
    )
    banner = ft.Container(
        content=text,
        bgcolor=DS.palette.success,
        padding=DS.pad.status_banner,
        border_radius=DS.radius.card,
        visible=False,
        width=width,
        alignment=ft.Alignment(0, 0),
    )
    return banner, text


async def show_status(
    banner: ft.Container | None,
    text: ft.Text | None,
    message: str,
    *,
    ok: bool,
    auto_hide_sec: float = 0.0,
) -> None:
    """Display `message` in the banner, coloured by `ok` (green) / not-ok (red).

    Success banners typically auto-fade (`auto_hide_sec > 0`); error banners
    persist (`auto_hide_sec = 0`, the default). No-ops if the banner/text were
    never built. Every `update()` is guarded so a not-yet-mounted (or torn-down)
    banner never raises."""
    if banner is None or text is None:
        return
    text.value = message
    banner.bgcolor = DS.palette.success if ok else DS.palette.danger
    banner.visible = True
    try:
        banner.update()
    except Exception:  # noqa: BLE001 — not mounted yet; value still applied
        pass
    if auto_hide_sec > 0:
        await asyncio.sleep(auto_hide_sec)
        banner.visible = False
        try:
            banner.update()
        except Exception:  # noqa: BLE001 — view may have been popped meanwhile
            pass
