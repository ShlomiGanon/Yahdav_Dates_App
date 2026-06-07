"""Shared screen-layout PRIMITIVES + tokens — the low-level toolkit the engine
(`BaseView`) composes into the full screen frame.

The structural COMPOSITION (HUB vs CONTENT, the card-over-action-bar layout, the
centered hub card, the overlay Stack) lives in `views/_base.py` — `BaseView` is the
single home of structural-layout decisions. This module keeps only the reusable
primitives it builds from: the full-screen background, the translucent card, the
shared Error Component + `guard`, the responsive-clamp math, and the runtime
action-bar helpers. All concrete values come from the Design System (re-exported
here via `utils.constants` for back-compat).
"""
from __future__ import annotations

import enum
import logging

import flet as ft

from style.design_system import DS
from utils.constants import AssetPaths, UIConstants, ThemeColors, TextSizes

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


# ----------------------------------------------------------------------------
# Content-screen geometry tokens — re-exported from `UIConstants` (which now
# pulls from the Design System) for the views/engine that import them by name.
# ----------------------------------------------------------------------------
CONTENT_CARD_MARGIN = UIConstants.CONTENT_CARD_MARGIN
CONTENT_CARD_PADDING = UIConstants.CONTENT_CARD_PADDING
CONTENT_CARD_PADDING_TALL = UIConstants.CONTENT_CARD_PADDING_TALL
CONTENT_BODY_SPACING = UIConstants.CONTENT_BODY_SPACING
ACTION_BAR_PADDING = UIConstants.ACTION_BAR_PADDING
ACTION_BAR_SPACING = UIConstants.ACTION_BAR_SPACING

# The Buttons Area is a single persistent container whose explicit height is
# animated. `DEFAULT_ACTION_HEIGHT` is the per-row fallback when an action does
# not declare its own `.height` (the shared button factories set BUTTON_HEIGHT);
# `ACTION_BAR_ANIM` is the implicit-animation spec that makes a height change
# tween instead of snap. The engine (`BaseView`) builds the animated box; this
# module owns the primitives it reuses (`action_bar_height`, `_center_fixed_width`)
# and the runtime swap (`set_actions`).
DEFAULT_ACTION_HEIGHT = UIConstants.BUTTON_HEIGHT
ACTION_BAR_ANIM = ft.Animation(UIConstants.ANIM_MS, ft.AnimationCurve.EASE_IN_OUT)
# Identity tag on the animated buttons container, so `action_bar_of()` /
# `set_actions()` can locate it on a built view without a fragile index walk.
_BUTTONS_BOX_TAG = "screen_shell_buttons"

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
            ft.Icon(ft.Icons.ERROR_OUTLINE, size=DS.sizing.icon_lg, color=ThemeColors.DANGER),
            ft.Text(
                message,
                size=TextSizes.H2,
                weight=ft.FontWeight.BOLD,
                color=ThemeColors.TEXT_MAIN,
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
# Screen-type / scroll-intent enums — declared by a screen, applied by BaseView
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


class ScreenType(enum.Enum):
    """The single discriminator that decides a screen's whole frame.

    HUB: a centered, max-width, semi-transparent card with the body AND the
        actions stacked INSIDE it — no sticky action bar. The shared baseline for
        Welcome / Login / Signup / Main Menu / placeholder / error / boot.
    CONTENT: a scrollable body card OVER a sticky, animated action bar. Profile,
        Discover, Chat, Matches, the photo screens, the read-only peer screens.
    """

    HUB = "hub"
    CONTENT = "content"


# Identity tag on the responsive hub card, so `responsive_card_of()` can locate
# it on a built view (for the live resize clamp) without a fragile index walk.
_HUB_CARD_TAG = "screen_shell_hub_card"


def clamp_hub_width(page_width: float | None) -> float | None:
    """Clamp the hub card width to `[CARD_MIN_WIDTH, CARD_MAX_WIDTH]` against the
    window (minus side margins). Returns None when the window width isn't known
    yet (first frame) so the card stays content-sized until the first resize."""
    if not page_width:
        return None
    available = page_width - 2 * UIConstants.HUB_SIDE_MARGIN
    return max(UIConstants.CARD_MIN_WIDTH, min(UIConstants.CARD_MAX_WIDTH, available))


def responsive_card(card_content: ft.Control, *, width: float | None = None) -> ft.Container:
    """A `translucent_card` tagged + (optionally) width-bounded for the hub.

    Default width is None → content-sized (never wider than its 400-px controls,
    so it never stretches on a wide window). `BaseView` sets an explicit clamped
    width on resize so the card shrinks gracefully on a narrow window; the hub
    content column STRETCHes, so the controls flex with the card width."""
    card = translucent_card(card_content, padding=UIConstants.CARD_PADDING)
    card.width = width
    card.data = _HUB_CARD_TAG
    return card


def responsive_card_of(view: ft.View) -> ft.Container | None:
    """Return the responsive hub card of a HUB view (for the live resize clamp),
    or None for a CONTENT view (whose card is full-bleed)."""
    content = getattr(view.controls[0], "content", None)
    if isinstance(content, ft.Column):
        for ctrl in content.controls:
            if getattr(ctrl, "data", None) == _HUB_CARD_TAG:
                return ctrl
    return None


def action_bar_height(actions: list[ft.Control]) -> float:
    """Deterministic pixel height of the Buttons Area for `actions`.

    Sums each action's explicit `.height` (the shared `create_*_button` factories
    set `BUTTON_HEIGHT`; a non-button action such as a divider or a send-row
    should declare its own height) falling back to `DEFAULT_ACTION_HEIGHT`, plus
    the inter-row spacing. Status banners are NOT included — they sit OUTSIDE the
    animated box so a banner toggling visibility never clips or jitters buttons.
    """
    rows = [(getattr(a, "height", None) or DEFAULT_ACTION_HEIGHT) for a in actions]
    return sum(rows) + ACTION_BAR_SPACING * max(0, len(rows) - 1)


def _center_fixed_width(ctrl: ft.Control) -> ft.Control:
    """Engine-owned action alignment: a fixed-width action (a 400px button) is
    re-centred inside a full-width wrapper; an expanding action (a send-row whose
    composer fills the bar) is left to span. This lets the action column use one
    canonical STRETCH alignment while every button still looks centred — the view
    never passes an alignment knob."""
    if getattr(ctrl, "width", None) is not None and not getattr(ctrl, "expand", False):
        return ft.Container(content=ctrl, alignment=ft.Alignment(0, 0))
    return ctrl


def action_bar_of(view: ft.View) -> ft.Container:
    """Return the animated Buttons-Area container of a CONTENT view, so a mounted
    view can later `set_actions()` on it. Locates it by tag rather than a brittle
    index walk."""
    content = view.controls[0].content
    # With an overlay the content is a Stack([layout, overlay]); without one it
    # IS the layout Column. Either way the action region is the layout's 2nd child.
    layout = content.controls[0] if isinstance(content, ft.Stack) else content
    region = layout.controls[1]
    for ctrl in region.content.controls:
        if getattr(ctrl, "data", None) == _BUTTONS_BOX_TAG:
            return ctrl
    # Deterministic fallback: the buttons box is always the region's last child.
    return region.content.controls[-1]


def set_actions(buttons_box: ft.Container, actions: list[ft.Control]) -> None:
    """Replace the Buttons-Area actions at runtime and animate the height change.

    Swaps the box's controls and recomputes its explicit height; the subsequent
    `update()` lets Flet tween the expand/contract. Call from a mounted view (e.g.
    once async data resolves and an extra action becomes relevant)."""
    buttons_box.content.controls = [_center_fixed_width(a) for a in actions]
    buttons_box.height = action_bar_height(actions)
    buttons_box.update()


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
            "stretched": bool(card_w and card_w > UIConstants.CARD_MAX_WIDTH),
            "fits": bool(card_w and card_w <= w),
        })
    return report
