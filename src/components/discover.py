"""Discover candidate tile — a single tappable member row for the Discover feed:
initials avatar (far right) with a presence dot, name + meta line filling the
space to its left, all on the shared member-row card. Composes the shared
`create_initial_avatar` + `create_member_row_card` so the view supplies only
data — the row's look is owned entirely by `create_member_row_card` (also used
by the Matches/chat-history thread list), so both lists render identically."""
import flet as ft

from components.avatars import create_initial_avatar
from components.cards import create_member_row_card
from style.design_system import DS

# Tap-target geometry. The card clears BUTTON_HEIGHT (70px) with headroom for a
# two-line name+meta stack — the 50+ audience needs generous targets.
_CARD_HEIGHT: int = DS.sizing.tile_h        # 86px
_AVATAR_DIAMETER: int = DS.sizing.avatar_sm  # 52px


def create_candidate_tile(
    name: str,
    meta: str,
    *,
    online: bool,
    on_click,
) -> ft.Control:
    """A single tappable candidate row: a presence-dot avatar (far right, RTL-
    native) plus the shared member-row layout (`create_member_row_card`) for
    the name/meta details. `on_click` receives the Flet control event."""
    avatar = create_initial_avatar(name, diameter=_AVATAR_DIAMETER, online=online)
    return create_member_row_card(avatar, name, meta, on_click=on_click, height=_CARD_HEIGHT)
