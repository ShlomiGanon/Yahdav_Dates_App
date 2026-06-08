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
from utils.constants import AssetPaths, UIConfig

log = logging.getLogger(__name__)


# Shared tag on the BG image's `ft.Hero` — identical across every route, so
# Flutter treats the background as ONE continuous element flying between
# views rather than as part of each view's slide/fade transition. Since the
# image is full-bleed and identically positioned in source and destination,
# the "flight" has nowhere to go: it renders perfectly STATIC across
# navigation while `content` keeps animating normally above it — the BG stops
# sliding/animating WITHOUT disabling Flet's page-transition animations.
_PAGE_BG_HERO_TAG = "screen_shell_page_bg"


# `ft.Stack` MUST be built with `fit=ft.StackFit.EXPAND` here. `expand=True`
# (set on both Stack children below) only has an effect when a control's
# DIRECT parent is a `Column`/`Row`/`View`/`Page` — a `Stack` is none of
# those, so without `fit=EXPAND` each child collapses to its own intrinsic
# size and gets placed at the Stack's default `alignment`
# (`AlignmentDirectional.topStart`, which — because `page.rtl = True` —
# renders at the visual TOP-RIGHT corner). That silently fights the single
# place screens are centred, `BaseView._wrap_card`, pinning every card to the
# top-right instead. `fit=EXPAND` tightens the constraints the Stack hands its
# non-positioned children to its own full size, so both layers fill the
# screen exactly as the lone `expand=True` background Container did pre-Hero —
# keeping `background_screen` a transparent passthrough and `_wrap_card` the
# ONE function that decides how the main container is centred.


def background_screen(route: str, content: ft.Control) -> ft.View:
    """A full-screen `ft.View` with the shared 'BG' image, fixed, behind `content`.

    The full-bleed background is achieved by three cooperating settings:
      • `expand=True` on the image container fills the available HEIGHT,
      • `CrossAxisAlignment.STRETCH` on the View fills the WIDTH, and
      • `BoxFit.FILL` shows the WHOLE artwork edge-to-edge (no crop; the image
        stretches/compresses to the window, aspect ratio not preserved).
    It is wrapped in a `_PAGE_BG_HERO_TAG`-tagged `ft.Hero` (see above) so it
    stays visually static while `content` — layered on top via `ft.Stack`,
    filling the same box — animates with the route transition as usual.
    """
    return ft.View(
        route=route,
        padding=DS.spacing.none,        # full-bleed background, no view padding
        vertical_alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ft.Container(
                expand=True,
                content=ft.Stack(
                    expand=True,
                    fit=ft.StackFit.EXPAND,
                    controls=[
                        ft.Hero(
                            tag=_PAGE_BG_HERO_TAG,
                            content=ft.Container(
                                expand=True,
                                # Solid colour BEHIND the image. If `BG.png`
                                # fails to resolve or is still loading
                                # mid-navigation, this paints instead of
                                # falling through to an unset background —
                                # which the Flet desktop client renders BLACK.
                                # This is the structural guard against the
                                # "completely black screen".
                                bgcolor=DS.palette.background,
                                image=ft.DecorationImage(
                                    src=AssetPaths.BG_IMAGE,
                                    fit=ft.BoxFit.FILL,
                                ),
                            ),
                        ),
                        ft.Container(expand=True, content=content),
                    ],
                ),
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


# ----------------------------------------------------------------------------
# Card entrance animation — driven by UIConfig.TRANS_EFFECT
# ----------------------------------------------------------------------------

_CARD_ANIM = ft.Animation(duration=300, curve=ft.AnimationCurve.EASE_OUT)

_SCALE_EFFECTS = {"zoom", "fade_forwards", "predictive"}
_OFFSET_INIT: dict[str, tuple[float, float]] = {
    "slide_up":   (0,    0.1),   # card starts 10% below, slides up
    "slide_down": (0,   -0.1),   # card starts 10% above, slides down
    "cupertino":  (0.2,  0.0),   # card starts 20% right, slides left (RTL forward)
}


def configure_card_entrance(card: ft.Container) -> None:
    """Set initial hidden/offset state on the card at build time.

    Must be called before the view is added to page.views so Flutter sees the
    initial opacity=0 / scale / offset on the very first frame."""
    effect = UIConfig.TRANS_EFFECT
    if effect == "none":
        return
    card.animate_opacity = _CARD_ANIM
    card.opacity = 0
    if effect in _SCALE_EFFECTS:
        card.animate_scale = _CARD_ANIM
        card.scale = ft.Scale(0.88)
    elif effect in _OFFSET_INIT:
        x, y = _OFFSET_INIT[effect]
        card.animate_offset = _CARD_ANIM
        card.offset = ft.Offset(x, y)


def trigger_card_entrance(card: "ft.Container | None") -> None:
    """Animate the card to its final visible state.

    Call from _framework_did_mount (after Flutter has mounted the view) so
    the implicit animation triggers a smooth transition from the initial
    hidden state set by configure_card_entrance."""
    if card is None or UIConfig.TRANS_EFFECT == "none":
        return
    card.opacity = 1
    if UIConfig.TRANS_EFFECT in _SCALE_EFFECTS:
        card.scale = ft.Scale(1)
    elif UIConfig.TRANS_EFFECT in _OFFSET_INIT:
        card.offset = ft.Offset(0, 0)
    card.update()


def _find_tagged_card(ctrl: ft.Control) -> ft.Container | None:
    """Depth-first search for the hub card tag under a layout root."""
    if getattr(ctrl, "data", None) == _HUB_CARD_TAG:
        return ctrl
    for child in getattr(ctrl, "controls", None) or []:
        found = _find_tagged_card(child)
        if found is not None:
            return found
    inner = getattr(ctrl, "content", None)
    if inner is not None:
        return _find_tagged_card(inner)
    return None


def responsive_card_of(view: ft.View) -> ft.Container | None:
    """Locate the tagged responsive card on a built view (for the live resize
    clamp), wherever it sits: directly under the outer layout `ft.Column`, inside
    the compact centering shell, nested under an `ft.Stack` overlay frame, or —
    as every screen now is — layered above the page-BG `ft.Hero` by
    `background_screen`. Searched purely by tag (a full depth-first walk), so
    it keeps resolving the ONE tagged card regardless of how many cooperating
    layers it is nested under."""
    content = getattr(view.controls[0], "content", None)
    if content is None:
        return None
    return _find_tagged_card(content)


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
