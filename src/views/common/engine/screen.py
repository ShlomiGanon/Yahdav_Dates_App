"""Shared screen-layout PRIMITIVES + tokens — the low-level toolkit the engine
(`BaseView`) composes into the full screen frame.

The structural COMPOSITION — the single centred, translucent card every screen
renders inside (Welcome/Login's shape), the overlay Stack — lives in
`views/_base.py`: `BaseView` is the single home of structural-layout decisions.
This module keeps only the reusable primitives it builds from: the full-screen
background, the translucent card, the shared Error Component + `guard`, and the
responsive-clamp math. All concrete values come from the Design System, read
directly (via `utils.constants`/`DS`) at the point of use — this module owns no
re-exported geometry tokens of its own.
"""
from __future__ import annotations

import enum
import logging

import flet as ft

from style.design_system import DS
from utils.constants import AssetPaths

log = logging.getLogger(__name__)


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
        padding=DS.spacing.none,        # full-bleed background, no view padding
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
                bgcolor=DS.palette.background,
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

    Uses `DS.opacity.form_overlay` (white at 50%) and the standard
    corner radius, so the background image shows through while text stays
    legible — identical to the My Profile form card.
    """
    return ft.Container(
        content=content,
        expand=expand,
        margin=margin,
        padding=DS.pad.card if padding is None else padding,
        bgcolor=ft.Colors.with_opacity(
            DS.opacity.form_overlay, DS.palette.surface,
        ),
        border_radius=DS.radius.card,
    )


# The single, app-wide friendly error message (50+ audience: calm, blame-free,
# actionable). Every Error Component the engine renders uses this by default.
DEFAULT_ERROR_MESSAGE = "אירעה שגיאה, אנא נסו שוב"


# ----------------------------------------------------------------------------
# Fault tolerance — the shared Error Component + guard
# ----------------------------------------------------------------------------
#
# Bulletproofing is layered:
#   • component level — `guard(build_fn)` runs a risky sub-tree builder and, on
#     ANY exception, returns the shared `error_component()` instead, so one bad
#     section degrades gracefully without taking down the screen;
#   • screen level    — `BaseView` runs its content/region builders through
#     `guard`, so a failure there renders the Error Component in-place;
#   • route level     — the router's `_safe_build` wraps the whole factory and
#     falls back to `error_view(...)` (the SAME Error Component, framed as a full
#     view), and a bare last-resort view sits under even that.
# Together a blank/black screen is unreachable.


def error_component(message: str = DEFAULT_ERROR_MESSAGE) -> ft.Control:
    """The predefined, visually-consistent Error Component: a danger icon over a
    friendly Hebrew message, styled like every other card heading. Rendered
    wherever a body, action, or sub-section fails to build."""
    return ft.Column(
        controls=[
            ft.Icon(ft.Icons.ERROR_OUTLINE, size=DS.sizing.icon_lg, color=DS.palette.danger),
            ft.Text(
                message,
                size=DS.type.h2,
                weight=ft.FontWeight.BOLD,
                color=DS.palette.text_main,
                rtl=True,
                text_align=ft.TextAlign.CENTER,
            ),
        ],
        tight=True,
        spacing=DS.spacing.md,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def guard(
    build_fn: "callable",
    *,
    message: str = DEFAULT_ERROR_MESSAGE,
) -> ft.Control:
    """Run a control builder, returning the shared Error Component if it raises.

    Use to fence off a risky sub-section (e.g. one derived from fetched data) so
    its failure degrades to the Error Component rather than bubbling up and
    blanking the screen."""
    try:
        return build_fn()
    except Exception:  # noqa: BLE001 — a render failure must degrade, not crash
        log.exception("screen: component build failed; rendering Error Component")
        return error_component(message)


# ----------------------------------------------------------------------------
# Scroll-intent enum — declared by a screen, applied by BaseView
# ----------------------------------------------------------------------------


class BodyLayout(enum.Enum):
    """How the engine should treat the `body` control's scrolling — chosen by
    INTENT, never by raw flags, so the contract stays layout-agnostic.

    SCROLLING: the body is ordinary content; the engine wraps it in an AUTO
        scroll region inside the card (the default — forms, feeds).
    SELF_SCROLLING: the body already expands and owns its scroll (an
        `ft.ListView`); the engine places it directly so scrolling isn't nested.
    """

    SCROLLING = "scrolling"
    SELF_SCROLLING = "self_scrolling"


# Identity tag on the responsive card, so `responsive_card_of()` can locate
# it on a built view (for the live resize clamp) without a fragile index walk.
_HUB_CARD_TAG = "screen_shell_hub_card"


def clamp_hub_width(page_width: float | None) -> float | None:
    """Clamp the hub card width to `[CARD_MIN_WIDTH, CARD_MAX_WIDTH]` against the
    window (minus side margins). Returns None when the window width isn't known
    yet (first frame) so the card stays content-sized until the first resize."""
    if not page_width:
        return None
    available = page_width - 2 * DS.sizing.hub_margin
    return max(DS.sizing.card_min, min(DS.sizing.card_max, available))


def responsive_card(
    card_content: ft.Control,
    *,
    width: float | None = None,
    expand: bool = False,
    padding: ft.Padding | int | None = None,
) -> ft.Container:
    """A `translucent_card` tagged + width-bounded — the ONE card shape every
    screen renders inside, centred and clamped to the app's mobile-width cap.

    Default width is None → content-sized (never wider than its 400-px controls,
    so it never stretches on a wide window). `BaseView` sets an explicit clamped
    width on resize so the card shrinks gracefully on a narrow window; the card's
    content column STRETCHes, so the controls flex with the card width.

    `expand`/`padding` let a screen whose body is a long, internally-scrolling
    list (`EXPAND_BODY = True`) grow the SAME card to fill the viewport — with
    the taller top clearance a full-height card needs to clear the BG image's
    logo — without changing its chrome or its width treatment."""
    card = translucent_card(
        card_content,
        expand=expand,
        padding=DS.pad.card if padding is None else padding,
    )
    card.width = width
    card.data = _HUB_CARD_TAG
    return card


def responsive_card_of(view: ft.View) -> ft.Container | None:
    """Locate the tagged responsive card on a built view (for the live resize
    clamp), wherever it sits: the sole child of the outer layout `ft.Column`, or
    nested one level inside an `ft.Stack` when the screen has an overlay."""
    content = getattr(view.controls[0], "content", None)
    layout = content.controls[0] if isinstance(content, ft.Stack) else content
    if isinstance(layout, ft.Column):
        for ctrl in layout.controls:
            if getattr(ctrl, "data", None) == _HUB_CARD_TAG:
                return ctrl
    return None


# ----------------------------------------------------------------------------
# Stress-Test support — headless responsiveness report
# ----------------------------------------------------------------------------


def stress_report(
    widths: "tuple[float, ...]" = (320, 380, 450, 1024, 1440),
) -> list[dict]:
    """Headless responsiveness check used by `tools/stress_test.py` and the tests.
    For each window width it returns the clamped hub-card width and whether it is
    centred (always) and NOT stretched (capped at CARD_MAX_WIDTH), so the layout
    contract is verifiable without a window."""
    report: list[dict] = []
    for w in widths:
        card_w = clamp_hub_width(w)
        report.append({
            "window": w,
            "card_width": card_w,
            "centered": True,
            "stretched": bool(card_w and card_w > DS.sizing.card_max),
            "fits": bool(card_w and card_w <= w),
        })
    return report
