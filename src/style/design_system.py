"""The Global Design System — the SINGLE source of truth for every visual and
structural layout constant in the app.

This is THE file to edit to re-skin the whole application: change a token here
and every screen updates uniformly, because `BaseView` (the structural engine)
and the shared components pull all spacing/sizing/padding/radius/typography/colour
values from the one `DS` instance below.

Design
------
* **Frozen dataclasses** — every token group is an immutable `@dataclass(frozen=True)`,
  composed into one `DesignSystem` instance (`DS`). Assigning to a token raises
  `FrozenInstanceError`, so the constants can't be mutated at runtime.
* **Grouped by concern** — `Palette` (colours), `Typography` (font sizes), `Spacing`
  (the spacing scale), `Sizing` (widths/heights/diameters), `Radius`, `Pad`
  (ft.Padding/ft.Margin bundles), `Motion`, `Opacity`, and `BodyTemplate` (the ONE
  normalized body-layout rule the engine applies to every screen).
* **The single source of visual truth.** Screens and components read `DS.*`
  directly — `utils/constants.py` holds only config (asset paths, DB/storage/
  auth knobs, message/match types), no visual tokens.

Scope: this file holds LAYOUT/STYLE tokens only. Geometric `ft.Alignment` coords
(the RTL-immune rule) and domain constants (age bounds, payload caps, page sizes)
deliberately live elsewhere — they are not "UI theme".
"""
from __future__ import annotations

from dataclasses import dataclass, field

import flet as ft


@dataclass(frozen=True)
class Palette:
    """Brand + state + neutral colours (was `ThemeColors`)."""

    # Core
    primary: ft.Colors = ft.Colors.RED_900          # brand red — constructive actions
    secondary: ft.Colors = ft.Colors.BLUE_GREY_400  # navigation / session actions
    # States
    success: ft.Colors = ft.Colors.GREEN_700
    danger: ft.Colors = ft.Colors.RED_400
    warning: ft.Colors = ft.Colors.AMBER_600
    info: ft.Colors = ft.Colors.BLUE_400
    field_error: ft.Colors = ft.Colors.RED_ACCENT_700   # strong inline error red (50+ legibility)
    # Neutrals
    background: ft.Colors = ft.Colors.RED
    surface: ft.Colors = ft.Colors.GREY
    tile: ft.Colors = ft.Colors.WHITE               # member-row bg (chat/discover tiles)
    text_main: ft.Colors = ft.Colors.GREY_900
    text_on_primary: ft.Colors = ft.Colors.WHITE
    # Presence
    online: ft.Colors = ft.Colors.GREEN_ACCENT_400
    offline: ft.Colors = ft.Colors.GREY_400
    # Chat bubbles
    bubble_self: ft.Colors = ft.Colors.GREEN_100
    bubble_peer: ft.Colors = ft.Colors.GREY_200


@dataclass(frozen=True)
class Typography:
    """Font-size scale (was `TextSizes`)."""

    h1: int = 50        # main welcome titles
    h2: int = 25        # card titles
    button: int = 40    # button text
    body: int = 16      # standard labels
    input: int = 25     # input / oversized text (50+)
    small: int = 13     # descriptions / fine print


@dataclass(frozen=True)
class Spacing:
    """The named spacing scale — replaces raw 2/8/10/12/14/15/20 gaps."""

    none: int = 0
    xxs: int = 2
    sm: int = 8
    bar: int = 10       # action-bar inter-row gap
    md: int = 12
    body: int = 14      # canonical gap between body controls
    element: int = 15   # hub/form element gap
    lg: int = 20


@dataclass(frozen=True)
class Sizing:
    """Widths / heights / diameters — button & input geometry plus every
    component size that used to be a raw literal in a view or component."""

    # Hub card
    card_w: int = 400
    card_max: int = 460
    card_min: int = 300
    hub_margin: int = 16
    # Buttons / inputs (senior-friendly 400x70)
    button_w: int = 400
    button_h: int = 70
    input_w: int = 400
    input_h: int = 70
    # Avatars / photos
    avatar_sm: int = 52         # feed/thread row avatar
    avatar_lg: int = 104        # peer profile avatar
    main_photo: int = 180       # My Profile main picture
    thumb: int = 110            # additional-photos thumbnail
    album_tile_h: int = 240     # peer album tile
    close_btn: int = 56         # lightbox dismiss
    presence_dot: int = 16
    unread_badge: int = 34
    tile_h: int = 86            # discover/matches member row height
    # Loading ring
    loader: int = 50
    loader_stroke: int = 10
    # Composites
    send_btn_w: int = 140       # chat send button
    dob_part_w: int = 120       # DOB day/month dropdown
    dob_year_w: int = 124       # DOB year dropdown
    divider_h_tall: int = 28    # profile action-bar divider
    divider_h: int = 24         # chat action-bar divider
    divider_thickness: int = 1  # hairline divider line
    ring: int = 2               # presence-dot / avatar white ring width
    icon_sm: int = 22           # small inline icon (camera badge)
    icon_md: int = 30           # medium icon (lightbox close)
    icon_lg: int = 48           # large icon (error card)
    icon_xl: int = 64           # extra-large icon (broken-image tile)
    icon_xxl: int = 96          # fullscreen broken-image glyph


@dataclass(frozen=True)
class Radius:
    """Corner radii."""

    card: int = 15
    bubble: int = 16


@dataclass(frozen=True)
class Pad:
    """Interior padding / outer margin bundles. Scalars are plain ints; the
    `ft.Padding`/`ft.Margin` objects use `default_factory` (fresh instance per
    DS, never a shared mutable default)."""

    card: int = 30
    status_banner: int = 14
    bubble: int = 12
    section: int = 24            # error card / bottom-sheet interior padding
    badge: int = 6              # camera-badge interior padding
    lightbox_close: ft.Padding = field(default_factory=lambda: ft.Padding(0, 16, 16, 0))
    divider: ft.Padding = field(default_factory=lambda: ft.Padding(0, 8, 0, 4))
    list_v: ft.Padding = field(default_factory=lambda: ft.Padding(0, 8, 0, 8))  # feed/chat ListView
    content_card: ft.Padding = field(default_factory=lambda: ft.Padding(20, 20, 20, 16))
    content_card_tall: ft.Padding = field(default_factory=lambda: ft.Padding(20, 40, 20, 16))
    list_tile: ft.Padding = field(default_factory=lambda: ft.Padding(16, 8, 16, 8))


@dataclass(frozen=True)
class Motion:
    """Animation timings."""

    anim_ms: int = 300


@dataclass(frozen=True)
class Opacity:
    """Translucency values."""

    form_overlay: float = 0.5    # 50%-white card over the BG image
    hover: float = 0.8           # primary button hover tint
    hover_alt: float = 0.85      # secondary button hover tint
    tile_bg: float = 0.25        # photo-tile / thumbnail backing
    badge: float = 0.55          # camera badge scrim
    scrim: float = 0.92          # fullscreen lightbox scrim
    loader_scrim: float = 0.53   # global blocking loading overlay (was #88000000)
    close_btn: float = 0.6       # lightbox dismiss button backing
    error_card: float = 0.12     # error-card danger-tinted backing
    thumb_icon: float = 0.35     # broken-image glyph size as a fraction of the tile


@dataclass(frozen=True)
class BodyTemplate:
    """The ONE normalized body-layout rule the engine (`BaseView`) applies to
    EVERY screen — so changing a value here reflows all screens uniformly."""

    spacing: int = 14                                            # body gap for ALL screens
    cross_align: ft.CrossAxisAlignment = ft.CrossAxisAlignment.STRETCH
    # Every screen's heading is centred — the one rule, Welcome/Login's shape.
    heading_align: ft.TextAlign = ft.TextAlign.CENTER


@dataclass(frozen=True)
class DesignSystem:
    """The composed design system. One immutable instance (`DS`) is the app-wide
    single source of truth for visual + structural layout."""

    palette: Palette = field(default_factory=Palette)
    type: Typography = field(default_factory=Typography)
    spacing: Spacing = field(default_factory=Spacing)
    sizing: Sizing = field(default_factory=Sizing)
    radius: Radius = field(default_factory=Radius)
    pad: Pad = field(default_factory=Pad)
    motion: Motion = field(default_factory=Motion)
    opacity: Opacity = field(default_factory=Opacity)
    body: BodyTemplate = field(default_factory=BodyTemplate)


# The single app-wide design system instance. Edit the dataclass defaults above
# (or construct a themed DesignSystem) to re-skin the entire UI.
DS = DesignSystem()
