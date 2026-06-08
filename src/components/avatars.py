"""Avatar + small circular indicator primitives.

The initials avatar (a brand-red circle with the member's first letter) and the
unread-count badge are shared by the Discover feed and the Matches list — kept
here so their circle geometry, colours and the presence-dot overlay are defined
once instead of inline per view."""
import flet as ft

from style.design_system import DS


def create_photo_avatar(src: str, name: str, *, diameter: float) -> ft.Control:
    """A circular profile picture rendered crash-proof on the CLIENT.

    Uses `ft.Image` with an `error_content` initials fallback — NOT
    `ft.DecorationImage` (which has no fallback). If the client can't load the
    src (a stale path, an unreadable/unsupported file), Flutter renders the
    initials circle instead of failing the render tree to a black screen; a solid
    `bgcolor` sits behind it as a second layer of safety."""
    initial = (name.strip()[:1] or "?").upper()
    return ft.Container(
        width=diameter,
        height=diameter,
        border_radius=diameter / 2,
        bgcolor=DS.palette.primary,
        alignment=ft.Alignment(0, 0),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Image(
            src=src,
            width=diameter,
            height=diameter,
            fit=ft.BoxFit.COVER,
            error_content=ft.Text(
                initial,
                size=DS.type.h1,
                weight=ft.FontWeight.BOLD,
                color=DS.palette.text_on_primary,
            ),
        ),
    )


def create_initial_avatar(
    name: str,
    *,
    diameter: float,
    online: bool | None = None,
    dot_diameter: float = DS.sizing.presence_dot,
) -> ft.Control:
    """A circular initials avatar (brand red, white initial).

    Args:
        diameter: the circle's width/height (callers keep their own size token).
        online: when not None, overlays a presence dot bottom-start — green
            (`ONLINE`) if True, grey (`OFFLINE`) if False. Omit for no dot.
        dot_diameter: presence-dot size when `online` is set.
    """
    initial = (name.strip()[:1] or "?").upper()
    circle = ft.Container(
        width=diameter,
        height=diameter,
        border_radius=diameter / 2,
        bgcolor=DS.palette.primary,
        alignment=ft.Alignment(0, 0),
        content=ft.Text(
            initial,
            size=DS.type.h2,
            weight=ft.FontWeight.BOLD,
            color=DS.palette.text_on_primary,
        ),
    )
    if online is None:
        return circle
    dot = ft.Container(
        width=dot_diameter,
        height=dot_diameter,
        border_radius=dot_diameter / 2,
        bgcolor=DS.palette.online if online else DS.palette.offline,
        # White ring lifts the dot off the avatar regardless of its colour.
        border=ft.border.all(DS.sizing.ring, DS.palette.surface),
    )
    return ft.Stack(
        controls=[
            circle,
            ft.Container(content=dot, alignment=ft.Alignment(-1, 1)),
        ],
        width=diameter,
        height=diameter,
    )


def create_unread_badge(count: int, *, diameter: float = DS.sizing.unread_badge) -> ft.Control:
    """Unread-count badge — a red circle with the number, for the far-left of a
    Matches thread row."""
    return ft.Container(
        width=diameter,
        height=diameter,
        border_radius=diameter / 2,
        bgcolor=DS.palette.danger,
        alignment=ft.Alignment(0, 0),
        content=ft.Text(
            str(count),
            size=DS.type.body,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE,
        ),
    )
