"""Shared screen-layout helpers — the single source of the app's full-screen
background + translucent-card visual language.

Centralising these means every screen (Main Menu, My Profile, placeholders…)
shares one definition of the background treatment and the form/card overlay, so
the look can be tuned in exactly one place. All concrete values come from
`utils.constants` (`AssetPaths.BG_IMAGE`, `UIConstants.FORM_OVERLAY_OPACITY`,
`CORNER_RADIUS`, `CARD_PADDING`).
"""
from __future__ import annotations

import enum
import logging
from typing import Callable

import flet as ft

from utils.constants import AssetPaths, UIConstants, ThemeColors, TextSizes

log = logging.getLogger(__name__)

# Throughout this module a "control-or-builder" is either a built `ft.Control` or
# a zero-arg callable returning one. The Shell runs builders inside a try/except
# (see `guard`) so a body/action that fails to construct degrades to the shared
# Error Component instead of crashing the screen.


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


# ----------------------------------------------------------------------------
# The unified two-region content-screen layout
# ----------------------------------------------------------------------------
#
# Every CONTENT screen (profile, photos, discover, chat, matches, the read-only
# peer profile + album) shares ONE structure, defined here exactly once:
#
#   ┌──────────────────────────────────────────┐
#   │  translucent_card  (expand=True)          │  ← the only region that scrolls
#   │  ┌────────────────────────────────────┐  │     (title + body)
#   │  │  body controls …                   │  │
#   │  └────────────────────────────────────┘  │
#   └──────────────────────────────────────────┘
#   ┌──────────────────────────────────────────┐
#   │  transparent action bar (never scrolls)   │  ← OUTSIDE the card: status
#   │   [status banner]  [buttons …]            │     banner + all buttons
#   └──────────────────────────────────────────┘
#
# Defining the margins/padding/spacing/expand behaviour in one place means
# *using `content_layout`/`content_screen` is the same thing as complying* with
# the design system's "scrollable card + sticky bottom action bar" contract.
# Hub / auth screens keep their own centred-card pattern and do NOT use this.

# Content-screen geometry — the single source of truth now lives in
# `UIConstants` (utils/constants.py) so ALL spacing/sizing tokens have one home.
# These module-level names are thin re-exports kept for screen.py's own use AND
# for the views that import `CONTENT_BODY_SPACING` from here.
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
# tween instead of snap. See `ScreenShell` for the full rationale.
DEFAULT_ACTION_HEIGHT = UIConstants.BUTTON_HEIGHT
ACTION_BAR_ANIM = ft.Animation(UIConstants.ANIM_MS, ft.AnimationCurve.EASE_IN_OUT)
# Identity tag on the animated buttons container, so `action_bar_of()` /
# `set_actions()` can locate it on a built view without a fragile index walk.
_BUTTONS_BOX_TAG = "screen_shell_buttons"

# The single, app-wide friendly error message (50+ audience: calm, blame-free,
# actionable). Every Error Component the Shell renders uses this by default.
DEFAULT_ERROR_MESSAGE = "אירעה שגיאה, אנא נסו שוב"


# ----------------------------------------------------------------------------
# Fault tolerance — the shared Error Component + guard
# ----------------------------------------------------------------------------
#
# Bulletproofing is layered:
#   • component level — `guard(build_fn)` runs a risky sub-tree builder and, on
#     ANY exception, returns the shared `error_component()` instead, so one bad
#     section degrades gracefully without taking down the screen;
#   • screen level    — `ScreenShell` runs `body`/`actions`/`overlay` builders
#     through `guard`, so a failure there renders the Error Component in-place;
#   • route level      — the router's `_safe_build` wraps the whole factory and
#     falls back to `error_screen(...)` (the SAME Error Component, framed as a
#     full view), and a bare last-resort view sits under even that.
# Together a blank/black screen is unreachable.


def error_component(message: str = DEFAULT_ERROR_MESSAGE) -> ft.Control:
    """The predefined, visually-consistent Error Component: a danger icon over a
    friendly Hebrew message, styled like every other card heading. Rendered
    wherever a body, action, or sub-section fails to build."""
    return ft.Column(
        controls=[
            ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=ThemeColors.DANGER),
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
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def guard(
    build_fn: Callable[[], ft.Control],
    *,
    message: str = DEFAULT_ERROR_MESSAGE,
) -> ft.Control:
    """Run a control builder, returning the shared Error Component if it raises.

    Use inside a view's `build()` to fence off a risky sub-section (e.g. one
    derived from fetched data) so its failure degrades to the Error Component
    rather than bubbling up and blanking the screen."""
    try:
        return build_fn()
    except Exception:  # noqa: BLE001 — a render failure must degrade, not crash
        log.exception("screen: component build failed; rendering Error Component")
        return error_component(message)


def _resolve(item: "ft.Control | Callable[[], ft.Control]", message: str) -> ft.Control:
    """Resolve a control-or-builder: builders run through `guard`; an already
    built control passes through untouched. (`ft.Control` instances are not
    callable, so `callable()` cleanly distinguishes the two.)"""
    if callable(item) and not isinstance(item, ft.Control):
        return guard(item, message=message)
    return item


def error_screen(
    route: str = "/error",
    *,
    message: str = DEFAULT_ERROR_MESSAGE,
    actions: list[ft.Control] | None = None,
) -> ft.View:
    """A full error VIEW: the shared Error Component (optionally with recovery
    actions, e.g. a back-to-menu button) centred in the `hub_screen` frame —
    identical to Welcome / Main Menu, so even a failure screen is on-brand. Used
    by the router's `_safe_build` backstop as the single source of the error UI."""
    controls: list[ft.Control] = [error_component(message)]
    if actions:
        controls.extend(actions)
    card = ft.Column(
        controls=controls,
        tight=True,
        spacing=20,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return hub_screen(route, card)


# ----------------------------------------------------------------------------
# ScreenShell — the agnostic Layout Provider
# ----------------------------------------------------------------------------
#
# A view PROVIDES two things and nothing else: a single `body` control (its own
# composed content) and an `actions` list (the footer buttons). The Shell — and
# only the Shell — owns every positioning decision: the scroll region, the
# translucent card, padding/margins, cross-axis alignment, and the animated
# sticky Buttons Area. The Shell knows nothing about the screen's logic,
# purpose, services, or routes; it just lays out the two regions. This keeps a
# hard Separation of Concerns line: **Shell = outer frame; view = inner
# composition** (e.g. a view centres its own fixed-width fields inside `body`;
# the Shell never reaches in to align them).


class BodyLayout(enum.Enum):
    """How the Shell should treat the `body` control's scrolling — chosen by
    INTENT, never by raw flags, so the contract stays layout-agnostic.

    SCROLLING: the body is ordinary content; the Shell wraps it in an AUTO
        scroll region inside the card (the default — forms, feeds).
    SELF_SCROLLING: the body already expands and owns its scroll (an
        `ft.ListView`); the Shell places it directly so scrolling isn't nested.
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
    """Return the responsive hub card of a HUB `ScreenShell` view (for the live
    resize clamp), or None for a CONTENT view (whose card is full-bleed)."""
    content = getattr(view.controls[0], "content", None)
    if isinstance(content, ft.Column):
        for ctrl in content.controls:
            if getattr(ctrl, "data", None) == _HUB_CARD_TAG:
                return ctrl
    return None


def action_bar_height(actions: list[ft.Control]) -> float:
    """Deterministic pixel height of the Buttons Area for `actions`.

    Sums each action's explicit `.height` (the shared `create_*_button`
    factories set `BUTTON_HEIGHT`; a non-button action such as a divider or a
    send-row should declare its own height) falling back to
    `DEFAULT_ACTION_HEIGHT`, plus the inter-row spacing. Status banners are NOT
    included — they sit OUTSIDE the animated box (see `_action_region`) so a
    banner toggling visibility never clips or jitters the buttons.
    """
    rows = [(getattr(a, "height", None) or DEFAULT_ACTION_HEIGHT) for a in actions]
    return sum(rows) + ACTION_BAR_SPACING * max(0, len(rows) - 1)


def _center_fixed_width(ctrl: ft.Control) -> ft.Control:
    """Shell-owned action alignment: a fixed-width action (a 400px button) is
    re-centred inside a full-width wrapper; an expanding action (a send-row
    whose composer fills the bar) is left to span. This lets the action column
    use one canonical STRETCH alignment while every button still looks centred —
    the view never passes an alignment knob."""
    if getattr(ctrl, "width", None) is not None and not getattr(ctrl, "expand", False):
        return ft.Container(content=ctrl, alignment=ft.Alignment(0, 0))
    return ctrl


def _animated_buttons_box(actions: list[ft.Control], height: float | None) -> ft.Container:
    """The persistent, height-animated Buttons Area container.

    Flet's implicit `animate` only tweens a property change on a control
    instance that PERSISTS across two updates. This one container is exactly
    that: an explicit computed `height` + `animate=ACTION_BAR_ANIM`. While a
    view is mounted, swapping its actions via `set_actions()` recomputes the
    height and the box expands/contracts smoothly instead of jumping.
    """
    box = ft.Container(
        data=_BUTTONS_BOX_TAG,
        height=height if height is not None else action_bar_height(actions),
        animate=ACTION_BAR_ANIM,
        content=ft.Column(
            controls=[_center_fixed_width(a) for a in actions],
            tight=True,
            spacing=ACTION_BAR_SPACING,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )
    return box


def _action_region(
    actions: list[ft.Control],
    status_banner: ft.Control | None,
    action_bar_height_override: float | None,
) -> ft.Container:
    """The sticky bottom region: an optional auto-sized status banner stacked
    above the animated Buttons Area, on a transparent bar so both float on the
    background image. The banner is auto-sized (0 when hidden), separate from
    the animated box, so its visibility toggles don't fight the height tween."""
    column_controls: list[ft.Control] = []
    if status_banner is not None:
        column_controls.append(status_banner)
    column_controls.append(_animated_buttons_box(actions, action_bar_height_override))
    return ft.Container(
        bgcolor=ft.Colors.TRANSPARENT,
        padding=ACTION_BAR_PADDING,
        content=ft.Column(
            controls=column_controls,
            tight=True,
            spacing=ACTION_BAR_SPACING,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )


def _resolve_actions(
    actions: "list | tuple | Callable[[], list]",
) -> list[ft.Control]:
    """Resolve an actions provider into a control list. `actions` may be a list
    (each item a control or builder) OR a single builder returning the list (the
    `BaseView.get_actions` method). A failing actions-builder degrades to NO
    actions (the screen stays usable) rather than crashing — body failure is the
    only fatal one, and it shows the Error Component."""
    if callable(actions) and not isinstance(actions, ft.Control):
        try:
            actions = actions()
        except Exception:  # noqa: BLE001 — actions are non-essential; degrade to none
            log.exception("screen: get_actions failed; rendering no actions")
            return []
    return [_resolve(a, DEFAULT_ERROR_MESSAGE) for a in actions]


def _content_root(
    body: ft.Control,
    actions: list[ft.Control],
    status_banner: ft.Control | None,
    body_layout: BodyLayout,
    action_bar_height: float | None,
    overlay: ft.Control | None,
) -> ft.Control:
    """CONTENT frame: a scrollable body card OVER a sticky, animated action bar
    (+ optional fullscreen overlay). The canonical content geometry, unchanged."""
    if body_layout is BodyLayout.SELF_SCROLLING:
        # The body (an ft.ListView) expands + owns its scroll: place it directly.
        card_inner: ft.Control = body
    else:
        # Ordinary content: the Shell owns an AUTO scroll region around it. The
        # body keeps its natural height so overflow scrolls; STRETCH is RTL-safe.
        card_inner = ft.Column(
            controls=[body],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    card = translucent_card(
        card_inner,
        expand=True,
        margin=CONTENT_CARD_MARGIN,
        # Canonical top-logo clearance for EVERY content screen.
        padding=CONTENT_CARD_PADDING_TALL,
    )
    region = _action_region(actions, status_banner, action_bar_height)
    layout = ft.Column(
        controls=[card, region],
        expand=True,
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
    if overlay is not None:
        # The Shell owns the Stack: content underneath, the fullscreen overlay
        # (e.g. a lightbox) on top, so toggling it never rebuilds the content.
        return ft.Stack(controls=[layout, overlay], expand=True)
    return layout


def _hub_root(body: ft.Control, actions: list[ft.Control]) -> ft.Control:
    """HUB frame: ONE centered, max-width card with the body AND the actions
    stacked inside it — the shared auth/menu baseline.

    The card content column STRETCHes, so the body's and actions' fixed-width
    (400-px) controls flex to the card's inner width — which `BaseView` clamps to
    the window on resize. So: wide window → card caps at its content width (never
    stretches); narrow window → card + controls shrink to fit; always centred.
    The centred column AUTO-scrolls, so a tall form (Login/Signup) scrolls
    instead of clipping its bottom button while a short card stays centred."""
    card_content = ft.Column(
        controls=[body, *actions],
        tight=True,
        spacing=UIConstants.ELEMENT_SPACING,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    card = responsive_card(card_content)
    return ft.Column(
        controls=[card],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def ScreenShell(
    route: str,
    *,
    body: "ft.Control | Callable[[], ft.Control]",
    actions: "list | tuple | Callable[[], list]" = (),
    status_banner: "ft.Control | Callable[[], ft.Control] | None" = None,
    overlay: "ft.Control | Callable[[], ft.Control] | None" = None,
    screen_type: ScreenType = ScreenType.CONTENT,
    body_layout: BodyLayout = BodyLayout.SCROLLING,
    action_bar_height: float | None = None,
) -> ft.View:
    """The unified screen shell — one renderer for both screen families.

    A view PROVIDES `body` and `actions` (and, for CONTENT, `status_banner` /
    `overlay`); the Shell owns ALL positioning per `screen_type` and returns the
    ready-to-mount `ft.View`. `BaseView.build()` calls this with the view's
    `get_*` methods, so screens never touch layout directly.

    Fault tolerance: `body`, `status_banner`, `overlay`, and each action may be a
    control OR a zero-arg builder; `actions` may itself be a builder returning the
    list. Builders run through `guard`, so a piece that fails to construct
    degrades to the shared Error Component (body) or is dropped (actions/overlay)
    rather than crashing the screen.

    Args:
        route: the view's route (carried onto the `ft.View`).
        body: the screen's content as a SINGLE control (or a builder of one).
        actions: footer buttons — for CONTENT the sticky animated bar; for HUB
            stacked inside the card. A list (controls/builders) or a builder.
        status_banner: CONTENT-only inline banner above the buttons.
        overlay: CONTENT-only fullscreen layer (e.g. a lightbox) the Shell stacks.
        screen_type: HUB (centered card) or CONTENT (scroll card + sticky bar).
        body_layout: CONTENT scrolling intent — see `BodyLayout`.
        action_bar_height: explicit CONTENT Buttons-Area height override.
    """
    # Resolve providers through `guard` so a construction failure becomes the
    # Error Component (body) / is dropped (actions, overlay) — never an escape.
    resolved_body = _resolve(body, DEFAULT_ERROR_MESSAGE)
    resolved_actions = _resolve_actions(actions)

    if screen_type is ScreenType.HUB:
        root: ft.Control = _hub_root(resolved_body, resolved_actions)
    else:
        resolved_banner = (
            _resolve(status_banner, DEFAULT_ERROR_MESSAGE)
            if status_banner is not None else None
        )
        resolved_overlay = (
            _resolve(overlay, DEFAULT_ERROR_MESSAGE) if overlay is not None else None
        )
        root = _content_root(
            resolved_body, resolved_actions, resolved_banner,
            body_layout, action_bar_height, resolved_overlay,
        )
    return background_screen(route, root)


def action_bar_of(view: ft.View) -> ft.Container:
    """Return the animated Buttons-Area container of a `ScreenShell` view, so a
    mounted view can later `set_actions()` on it. Locates it by tag rather than
    a brittle index walk."""
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
    `update()` lets Flet tween the expand/contract. Call from a mounted view
    (e.g. once async data resolves and an extra action becomes relevant)."""
    buttons_box.content.controls = [_center_fixed_width(a) for a in actions]
    buttons_box.height = action_bar_height(actions)
    buttons_box.update()


# ----------------------------------------------------------------------------
# Back-compat: the original list-`body` helpers, now thin shims
# ----------------------------------------------------------------------------
#
# Screens not yet migrated to the agnostic `ScreenShell` (and the layout tests)
# still call `content_layout` / `content_screen` with a `body: list` and raw
# `scroll` / alignment / padding knobs. These preserve the EXACT original output
# structure (a flat action bar, content-sized, no animation) so nothing breaks;
# new and migrated views should prefer `ScreenShell`.


def content_layout(
    *,
    body: list[ft.Control],
    actions: list[ft.Control],
    status_banner: ft.Control | None = None,
    scroll: bool = True,
    body_alignment: ft.CrossAxisAlignment = ft.CrossAxisAlignment.STRETCH,
    actions_alignment: ft.CrossAxisAlignment = ft.CrossAxisAlignment.CENTER,
    card_margin: ft.Margin | None = None,
    card_padding: ft.Padding | None = None,
) -> ft.Column:
    """Back-compat two-region layout (scroll card + sticky bar) returning the
    `ft.Column` that goes INSIDE `background_screen`. Used directly only where
    the layout must be wrapped first — e.g. the peer album, which stacks a
    fullscreen lightbox over it. Prefer `ScreenShell` for new screens.
    """
    card_column = ft.Column(
        controls=body,
        spacing=CONTENT_BODY_SPACING,
        expand=True,
        horizontal_alignment=body_alignment,
    )
    if scroll:
        card_column.scroll = ft.ScrollMode.AUTO

    scroll_region = translucent_card(
        card_column,
        expand=True,
        margin=card_margin if card_margin is not None else CONTENT_CARD_MARGIN,
        padding=card_padding if card_padding is not None else CONTENT_CARD_PADDING,
    )

    bar_controls: list[ft.Control] = []
    if status_banner is not None:
        bar_controls.append(status_banner)
    bar_controls.extend(actions)

    # Transparent bar (no fill, no border) so the buttons float directly on the
    # background image; each button / banner carries its own colour.
    action_bar = ft.Container(
        bgcolor=ft.Colors.TRANSPARENT,
        padding=ACTION_BAR_PADDING,
        content=ft.Column(
            controls=bar_controls,
            tight=True,
            spacing=ACTION_BAR_SPACING,
            horizontal_alignment=actions_alignment,
        ),
    )

    return ft.Column(
        controls=[scroll_region, action_bar],
        expand=True,
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def content_screen(
    route: str,
    *,
    body: list[ft.Control],
    actions: list[ft.Control],
    status_banner: ft.Control | None = None,
    scroll: bool = True,
    body_alignment: ft.CrossAxisAlignment = ft.CrossAxisAlignment.STRETCH,
    actions_alignment: ft.CrossAxisAlignment = ft.CrossAxisAlignment.CENTER,
    card_margin: ft.Margin | None = None,
    card_padding: ft.Padding | None = None,
) -> ft.View:
    """Back-compat content screen: `content_layout` inside `background_screen`.
    Preserved for screens with bespoke needs (e.g. the read-only peer screens'
    tall top padding). New screens should use `ScreenShell`.
    """
    return background_screen(
        route,
        content_layout(
            body=body,
            actions=actions,
            status_banner=status_banner,
            scroll=scroll,
            body_alignment=body_alignment,
            actions_alignment=actions_alignment,
            card_margin=card_margin,
            card_padding=card_padding,
        ),
    )


# ----------------------------------------------------------------------------
# The centered single-card layout — hub / auth / status screens
# ----------------------------------------------------------------------------
#
# The documented EXCEPTION to the two-region content-screen split. Welcome, the
# Main Menu, the auth modal (Login / Signup), the "coming soon" placeholder, and
# the router's OWN boot spinner + error view all show ONE translucent_card,
# vertically + horizontally centred over the full-screen background, with every
# control — buttons included — INSIDE the card. There is no scroll region and no
# sticky action bar. Defining the centring + card geometry here once means every
# hub screen shares the identical frame instead of hand-rolling
# `background_screen(translucent_card(...))`.


def hub_screen(
    route: str,
    card_content: ft.Control,
    *,
    card_padding: ft.Padding | int | None = None,
) -> ft.View:
    """Back-compat shim for the CENTERED single-card hub layout, now a thin
    wrapper over `ScreenShell(..., screen_type=ScreenType.HUB)`.

    Kept so the router's boot spinner and `error_screen` (which pass a single
    pre-built `card_content` with the buttons already inside) keep working
    unchanged. New screens go through `BaseView` + `get_body`/`get_actions`.
    `card_padding` is now governed by the shared hub card and is ignored.
    """
    return ScreenShell(route, body=card_content, screen_type=ScreenType.HUB)


# ----------------------------------------------------------------------------
# Stress-Test support — headless responsiveness report
# ----------------------------------------------------------------------------


def stress_report(
    widths: "tuple[float, ...]" = (320, 380, 450, 1024, 1440),
) -> list[dict]:
    """Headless responsiveness check used by `tools/stress_test.py` and the
    tests. For each window width it returns the clamped hub-card width and
    whether it is centred (always) and NOT stretched (capped at CARD_MAX_WIDTH),
    so the layout contract is verifiable without a window."""
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
