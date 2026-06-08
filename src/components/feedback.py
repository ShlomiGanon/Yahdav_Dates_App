"""Shared user-feedback primitives: per-field validation error labels and the
inline status banner (success/error) with its show/hide helper.

Centralising these means a view never hand-rolls an error `ft.Text` or a banner
`ft.Container` again — using the primitive IS complying with the design system.
"""
import asyncio

import flet as ft

from style.design_system import DS


# ----------------------------------------------------------------------------
# Per-field validation error labels
# ----------------------------------------------------------------------------


def create_field_error_label() -> ft.Text:
    """A hidden, high-visibility, RTL error label sized for the 50+ audience.

    Shown beneath an input via `set_field_error`; one message at a time so a
    senior sees exactly which field failed and why. The colour comes from
    `DS.palette.field_error` (no raw hex in views)."""
    return ft.Text(
        value="",
        size=DS.type.input,
        color=DS.palette.field_error,
        weight=ft.FontWeight.W_500,
        rtl=True,
        text_align=ft.TextAlign.RIGHT,
        visible=False,
        selectable=False,
    )


def set_field_error(label: ft.Text, message: str) -> None:
    """Show `message` on a field error label and push it to the client. Safe to
    call from a mounted view (a detached label silently no-ops on update)."""
    label.value = message
    label.visible = bool(message)
    try:
        label.update()
    except Exception:  # noqa: BLE001 — not yet mounted; the value still sticks
        pass


def clear_field_errors(*labels: ft.Text) -> None:
    """Reset one or more field error labels to hidden/empty. Does NOT call
    `update()` — the caller flushes once (typically via `page.update()`) so a
    multi-field clear is a single repaint."""
    for label in labels:
        label.value = ""
        label.visible = False


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
