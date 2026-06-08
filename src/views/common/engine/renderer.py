"""Declarative UI schema + the `ViewRenderer` engine.

A screen describes its UI as DATA — a tree of `UIComponent` nodes wrapped in a
`ViewContent` — and the renderer materialises that data into Flet controls by
delegating to the shared component factories (`src/components/*`) and the screen
primitives (`views/common/helpers/photos`, `views/common/engine/screen`). The screen never
touches Flet construction directly; the renderer is the single place that knows
how a `Kind` becomes a control, so the RTL recipe and the `DS` tokens live in ONE
place.

Design (locked with the project owner)
--------------------------------------
* TOTAL vocabulary — every control the app uses has a `Kind`, factory-backed
  (HEADING, PRIMARY_BUTTON, TEXT_FIELD, CHAT_BUBBLE, …) AND raw Flet primitives
  (COLUMN, ROW, STACK, TEXT, CHECKBOX, LISTVIEW, DROPDOWN, …).
* Refs via pre-build + `RAW` — the renderer keeps NO key→control registry and is
  pure/side-effect-free. A view that mutates a control in a handler (an input's
  `.value`, a list's `.controls`) PRE-BUILDS that control (usually via the same
  factory) and embeds it as `raw(ctrl)`, holding the ref itself.
* Faithful output — factory-backed kinds call the factory verbatim and primitive
  kinds pass the caller's kwargs straight through, so a migrated screen renders a
  byte-identical control tree to the hand-written original.

Fault tolerance (Engineering Contract §3 / Peer Layout Boundary Rule)
---------------------------------------------------------------------
Every node is built through `screen.guard(...)`, so a node that fails to
construct degrades to the shared Error Component in place instead of bubbling up
and blanking the screen — the same component ring `BaseView` already applies to
its body region (`guard(self._render_body)`). The renderer only materialises
STATIC, build()-time scaffolding; dynamically-loaded list rows (Discover
candidates, Chat bubbles, Matches threads) keep flowing through
`views.common.helpers.safe_list.build_items_safe` into a PRE-BUILT container embedded
via `raw(...)`, so the per-row isolation is unchanged.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, NamedTuple

import flet as ft

from components.avatars import (
    create_initial_avatar,
    create_photo_avatar,
    create_unread_badge,
)
from components.buttons import create_primary_button, create_secondary_button
from components.cards import create_tile_card
from components.chat import create_chat_bubble
from components.discover import create_candidate_tile
from components.feedback import create_field_error_label, create_status_banner
from components.inputs import create_hebrew_text_field
from components.profile_fields import create_profile_field
from components.typography import create_screen_heading, create_section_heading
from views.common.helpers.photos import photo_thumb
from views.common.engine.screen import DEFAULT_ERROR_MESSAGE, error_component, guard


class Kind(enum.Enum):
    """The complete node vocabulary. Factory-backed kinds map to a shared
    `src/components` factory; primitive kinds construct a raw Flet control; `RAW`
    passes a pre-built control through untouched (the only ref mechanism)."""

    # --- factory-backed (src/components/*) ---
    HEADING = "heading"
    SECTION_HEADING = "section_heading"
    PRIMARY_BUTTON = "primary_button"
    SECONDARY_BUTTON = "secondary_button"
    TEXT_FIELD = "text_field"
    FIELD_ERROR = "field_error"
    STATUS_BANNER = "status_banner"
    CHAT_BUBBLE = "chat_bubble"
    PROFILE_FIELD = "profile_field"
    CANDIDATE_TILE = "candidate_tile"
    TILE_CARD = "tile_card"
    PHOTO_AVATAR = "photo_avatar"
    INITIAL_AVATAR = "initial_avatar"
    UNREAD_BADGE = "unread_badge"
    PHOTO_THUMB = "photo_thumb"
    ERROR = "error"

    # --- raw Flet primitives (total coverage) ---
    COLUMN = "column"
    ROW = "row"
    CONTAINER = "container"
    STACK = "stack"
    TEXT = "text"
    ICON = "icon"
    IMAGE = "image"
    DIVIDER = "divider"
    CHECKBOX = "checkbox"
    LISTVIEW = "listview"
    DROPDOWN = "dropdown"

    # --- escape hatch ---
    RAW = "raw"


@dataclass(frozen=True)
class UIComponent:
    """One node of the UI schema.

    `text` carries the primary string (a heading/button label, a Text value, an
    icon name, a profile-field label). `children` are sub-nodes for containers.
    `on_click`/`on_submit` are event handlers. `control` holds a pre-built control
    for `RAW`. `props` carries every other kind-specific keyword, passed straight
    through to the factory or Flet constructor so output is faithful."""

    kind: Kind
    text: str | None = None
    children: tuple["UIComponent", ...] = ()
    on_click: Callable | None = None
    on_submit: Callable | None = None
    control: ft.Control | None = None
    props: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ViewContent:
    """A screen's whole UI as data: the single `body` root plus the optional
    action/banner/overlay regions and any Flet services to attach. Mirrors the
    `BaseView` provider surface (`get_body`/`get_actions`/`get_status_banner`/
    `get_overlay`/`get_services`) one-to-one."""

    body: UIComponent
    actions: tuple[UIComponent, ...] = ()
    status_banner: UIComponent | None = None
    overlay: UIComponent | None = None
    services: tuple[ft.Control, ...] = ()


class RenderedView(NamedTuple):
    """The materialised regions, handed back to the `BaseView` providers so each
    `get_*` returns its part (identity-stable within a single build)."""

    body: ft.Control
    actions: list[ft.Control]
    status_banner: ft.Control | None
    overlay: ft.Control | None
    services: list[ft.Control]


# ----------------------------------------------------------------------------
# The renderer engine
# ----------------------------------------------------------------------------


class ViewRenderer:
    """Stateless engine that turns a `UIComponent`/`ViewContent` into Flet
    controls. One shared instance is enough — it holds no per-view state."""

    def render(self, node: UIComponent) -> ft.Control:
        """Materialise a single node, fault-isolated: a build failure degrades to
        the shared Error Component (never an escape / black screen)."""
        return guard(lambda: self._build(node), message=DEFAULT_ERROR_MESSAGE)

    def render_all(self, nodes: "tuple[UIComponent, ...] | list[UIComponent]") -> list[ft.Control]:
        """Materialise a list of nodes, each one fault-isolated."""
        return [self.render(n) for n in nodes]

    def render_content(self, content: ViewContent) -> RenderedView:
        """Materialise a whole `ViewContent` into its four regions + services."""
        return RenderedView(
            body=self.render(content.body),
            actions=self.render_all(content.actions),
            status_banner=(
                self.render(content.status_banner)
                if content.status_banner is not None else None
            ),
            overlay=(
                self.render(content.overlay)
                if content.overlay is not None else None
            ),
            services=list(content.services),
        )

    # -- dispatch ------------------------------------------------------------

    def _build(self, node: UIComponent) -> ft.Control:
        builder = _BUILDERS.get(node.kind)
        if builder is None:  # pragma: no cover — exhaustive map; defensive
            raise ValueError(f"ViewRenderer: no builder for {node.kind!r}")
        return builder(self, node)

    def _children(self, node: UIComponent) -> list[ft.Control]:
        """Render a container node's children, each fault-isolated."""
        return [self.render(c) for c in node.children]


# ----------------------------------------------------------------------------
# Per-kind builders — factory-backed kinds call the factory VERBATIM; primitive
# kinds pass the caller's kwargs straight through. `props` is always the exact
# kwargs the DSL helper captured, so the output matches the hand-written control.
# ----------------------------------------------------------------------------


def _b_heading(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return create_screen_heading(n.text, **n.props)


def _b_section_heading(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return create_section_heading(n.text, **n.props)


def _b_primary(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return create_primary_button(n.text, n.on_click, **n.props)


def _b_secondary(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return create_secondary_button(n.text, n.on_click, **n.props)


def _b_text_field(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return create_hebrew_text_field(n.text, on_submit=n.on_submit, **n.props)


def _b_field_error(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return create_field_error_label(**n.props)


def _b_status_banner(r: ViewRenderer, n: UIComponent) -> ft.Control:
    # The factory returns (container, text); a node yields the CONTAINER only.
    # A mutated banner needs the text ref too, so views pre-build it and pass
    # raw(container) — this node exists for vocabulary completeness.
    banner, _text = create_status_banner(**n.props)
    return banner


def _b_chat_bubble(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return create_chat_bubble(n.text, **n.props)


def _b_profile_field(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return create_profile_field(n.text, n.props["value"])


def _b_candidate_tile(r: ViewRenderer, n: UIComponent) -> ft.Control:
    props = dict(n.props)
    meta = props.pop("meta")
    return create_candidate_tile(n.text, meta, on_click=n.on_click, **props)


def _b_tile_card(r: ViewRenderer, n: UIComponent) -> ft.Control:
    content = r.render(n.children[0]) if n.children else None
    return create_tile_card(content, on_click=n.on_click, **n.props)


def _b_photo_avatar(r: ViewRenderer, n: UIComponent) -> ft.Control:
    props = dict(n.props)
    name = props.pop("name")
    return create_photo_avatar(n.text, name, **props)


def _b_initial_avatar(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return create_initial_avatar(n.text, **n.props)


def _b_unread_badge(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return create_unread_badge(n.props["count"], **{k: v for k, v in n.props.items() if k != "count"})


def _b_photo_thumb(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return photo_thumb(n.text, **n.props)


def _b_error(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return error_component(n.text or DEFAULT_ERROR_MESSAGE)


# -- primitive Flet controls ---------------------------------------------------
# Container kinds render children (fault-isolated); leaf kinds pass props through.
# COLUMN/ROW default to the RTL-safe STRETCH cross-axis (override via props); TEXT
# defaults to the RTL recipe (rtl=True + RIGHT). Defaults are overridable so a
# migrated control can be reproduced exactly.

_STRETCH = ft.CrossAxisAlignment.STRETCH


def _b_column(r: ViewRenderer, n: UIComponent) -> ft.Control:
    props = {"horizontal_alignment": _STRETCH, **n.props}
    return ft.Column(controls=r._children(n), **props)


def _b_row(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return ft.Row(controls=r._children(n), **n.props)


def _b_container(r: ViewRenderer, n: UIComponent) -> ft.Control:
    content = r.render(n.children[0]) if n.children else None
    return ft.Container(content=content, **n.props)


def _b_stack(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return ft.Stack(controls=r._children(n), **n.props)


def _b_text(r: ViewRenderer, n: UIComponent) -> ft.Control:
    props = {"rtl": True, "text_align": ft.TextAlign.RIGHT, **n.props}
    return ft.Text(n.text, **props)


def _b_icon(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return ft.Icon(n.text, **n.props)


def _b_image(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return ft.Image(**n.props)


def _b_divider(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return ft.Divider(**n.props)


def _b_checkbox(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return ft.Checkbox(**n.props)


def _b_listview(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return ft.ListView(controls=r._children(n), **n.props)


def _b_dropdown(r: ViewRenderer, n: UIComponent) -> ft.Control:
    return ft.Dropdown(**n.props)


def _b_raw(r: ViewRenderer, n: UIComponent) -> ft.Control:
    if n.control is None:
        raise ValueError("RAW node has no control")
    return n.control


_BUILDERS: dict[Kind, Callable[[ViewRenderer, UIComponent], ft.Control]] = {
    Kind.HEADING: _b_heading,
    Kind.SECTION_HEADING: _b_section_heading,
    Kind.PRIMARY_BUTTON: _b_primary,
    Kind.SECONDARY_BUTTON: _b_secondary,
    Kind.TEXT_FIELD: _b_text_field,
    Kind.FIELD_ERROR: _b_field_error,
    Kind.STATUS_BANNER: _b_status_banner,
    Kind.CHAT_BUBBLE: _b_chat_bubble,
    Kind.PROFILE_FIELD: _b_profile_field,
    Kind.CANDIDATE_TILE: _b_candidate_tile,
    Kind.TILE_CARD: _b_tile_card,
    Kind.PHOTO_AVATAR: _b_photo_avatar,
    Kind.INITIAL_AVATAR: _b_initial_avatar,
    Kind.UNREAD_BADGE: _b_unread_badge,
    Kind.PHOTO_THUMB: _b_photo_thumb,
    Kind.ERROR: _b_error,
    Kind.COLUMN: _b_column,
    Kind.ROW: _b_row,
    Kind.CONTAINER: _b_container,
    Kind.STACK: _b_stack,
    Kind.TEXT: _b_text,
    Kind.ICON: _b_icon,
    Kind.IMAGE: _b_image,
    Kind.DIVIDER: _b_divider,
    Kind.CHECKBOX: _b_checkbox,
    Kind.LISTVIEW: _b_listview,
    Kind.DROPDOWN: _b_dropdown,
    Kind.RAW: _b_raw,
}


# ----------------------------------------------------------------------------
# Ergonomic DSL — what screens actually write. Each returns a UIComponent; the
# kwargs are captured verbatim into `props` so the rendered control matches the
# factory/Flet call exactly.
# ----------------------------------------------------------------------------


def heading(text: str, *, center: bool = False) -> UIComponent:
    return UIComponent(Kind.HEADING, text=text, props={"center": center})


def section_heading(text: str, *, center: bool = False) -> UIComponent:
    return UIComponent(Kind.SECTION_HEADING, text=text, props={"center": center})


def primary_button(text: str, on_click: Callable, **props: Any) -> UIComponent:
    return UIComponent(Kind.PRIMARY_BUTTON, text=text, on_click=on_click, props=props)


def secondary_button(text: str, on_click: Callable, **props: Any) -> UIComponent:
    return UIComponent(Kind.SECONDARY_BUTTON, text=text, on_click=on_click, props=props)


def text_field(label: str, *, on_submit: Callable | None = None, **props: Any) -> UIComponent:
    return UIComponent(Kind.TEXT_FIELD, text=label, on_submit=on_submit, props=props)


def field_error() -> UIComponent:
    return UIComponent(Kind.FIELD_ERROR)


def status_banner(**props: Any) -> UIComponent:
    return UIComponent(Kind.STATUS_BANNER, props=props)


def chat_bubble(text: str, *, mine: bool) -> UIComponent:
    return UIComponent(Kind.CHAT_BUBBLE, text=text, props={"mine": mine})


def profile_field(label: str, value: str) -> UIComponent:
    return UIComponent(Kind.PROFILE_FIELD, text=label, props={"value": value})


def candidate_tile(name: str, meta: str, *, online: bool, on_click: Callable) -> UIComponent:
    return UIComponent(
        Kind.CANDIDATE_TILE, text=name, on_click=on_click,
        props={"meta": meta, "online": online},
    )


def tile_card(content: UIComponent, *, on_click: Callable, **props: Any) -> UIComponent:
    return UIComponent(Kind.TILE_CARD, children=(content,), on_click=on_click, props=props)


def photo_avatar(src: str, name: str, *, diameter: float) -> UIComponent:
    return UIComponent(Kind.PHOTO_AVATAR, text=src, props={"name": name, "diameter": diameter})


def initial_avatar(name: str, **props: Any) -> UIComponent:
    return UIComponent(Kind.INITIAL_AVATAR, text=name, props=props)


def unread_badge(count: int, **props: Any) -> UIComponent:
    return UIComponent(Kind.UNREAD_BADGE, props={"count": count, **props})


def photo_thumb_node(src: str, *, size: float) -> UIComponent:
    return UIComponent(Kind.PHOTO_THUMB, text=src, props={"size": size})


def error(message: str | None = None) -> UIComponent:
    return UIComponent(Kind.ERROR, text=message)


def column(children: "list[UIComponent] | tuple[UIComponent, ...]", **props: Any) -> UIComponent:
    return UIComponent(Kind.COLUMN, children=tuple(children), props=props)


def row(children: "list[UIComponent] | tuple[UIComponent, ...]", **props: Any) -> UIComponent:
    return UIComponent(Kind.ROW, children=tuple(children), props=props)


def container(child: UIComponent | None = None, **props: Any) -> UIComponent:
    children = (child,) if child is not None else ()
    return UIComponent(Kind.CONTAINER, children=children, props=props)


def stack(children: "list[UIComponent] | tuple[UIComponent, ...]", **props: Any) -> UIComponent:
    return UIComponent(Kind.STACK, children=tuple(children), props=props)


def text(value: str, **props: Any) -> UIComponent:
    return UIComponent(Kind.TEXT, text=value, props=props)


def icon(name: Any, **props: Any) -> UIComponent:
    return UIComponent(Kind.ICON, text=name, props=props)


def image(**props: Any) -> UIComponent:
    return UIComponent(Kind.IMAGE, props=props)


def divider(**props: Any) -> UIComponent:
    return UIComponent(Kind.DIVIDER, props=props)


def checkbox(**props: Any) -> UIComponent:
    return UIComponent(Kind.CHECKBOX, props=props)


def listview(children: "list[UIComponent] | tuple[UIComponent, ...]" = (), **props: Any) -> UIComponent:
    return UIComponent(Kind.LISTVIEW, children=tuple(children), props=props)


def dropdown(**props: Any) -> UIComponent:
    return UIComponent(Kind.DROPDOWN, props=props)


def raw(control: ft.Control) -> UIComponent:
    """Embed a PRE-BUILT control untouched — the escape hatch and the only way a
    view keeps a live ref to a control it mutates in a handler."""
    return UIComponent(Kind.RAW, control=control)
