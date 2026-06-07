"""MatchesView — chat history / active conversation threads ("היסטוריית שיחות").

Reached from the Main Menu's third option. Lists every conversation the logged-in
user has, newest first: contact avatar on the far right, name + last-message
preview to its left, and an unread-count badge on the far left. Tapping a row
opens that chat.

Architecture
------------
Depends on TWO role-interfaces, by genuine need (Interface Segregation):
  • `IMessagingService` — the conversation threads + unread counts.
  • `IProfileRepository` — resolve each peer's display name for the row.
The router injects both via `typing.cast`. Styling reuses the shared
full-screen 'BG' (`BoxFit.FILL`) + 50%-white `translucent_card`.

RTL note
--------
This build's `page.rtl=True` flips `CrossAxisAlignment.END` / `MainAxisAlignment`
to the LEFT, so right-alignment here uses the proven recipe instead: `STRETCH`
columns, RTL-native child order (first Row child renders rightmost), an
`expand` middle column, and absolute `text_align=RIGHT`.
"""
from __future__ import annotations
import asyncio
import logging

import flet as ft

from views._base import BaseView
from views.common.screen import BodyLayout, CONTENT_BODY_SPACING
from views.common.navigation import back_to_menu_button
from components import loading
from services.I_Messaging_Service import IMessagingService
from services.I_Profile_Repository import IProfileRepository
from utils.constants import TextSizes, UIConstants, ThemeColors

log = logging.getLogger(__name__)


class MatchesView(BaseView):
    """Vertical list of the user's chat threads, right-anchored for Hebrew."""

    ROUTE = "/chat/history"

    SESSION_USER_ID_KEY  = "current_user_id"
    SELECTED_PEER_ID_KEY = "selected_peer_id"   # read by ChatView on open

    _CHAT_ROUTE  = "/chat/new"        # opening a thread → the chat screen
    _MENU_ROUTE  = "/menu"            # the top "back" button
    _DISCOVER_ROUTE = "/matching/discover"

    _CARD_HEIGHT: int = UIConstants.BUTTON_HEIGHT + 16   # 86px row
    _AVATAR_DIAMETER: int = 52
    _BADGE_DIAMETER: int = 34
    _PREVIEW_MAX_CHARS: int = 38

    def __init__(
        self,
        page: ft.Page,
        messaging: IMessagingService,
        profiles: IProfileRepository,
    ) -> None:
        super().__init__(page)
        self.messaging = messaging
        self.profiles = profiles
        # Set on navigate-away so an in-flight load stops touching the page.
        self._closing: bool = False

    # ============================================================
    #  Layout
    # ============================================================

    BODY_LAYOUT = BodyLayout.SELF_SCROLLING   # the ListView owns its own scroll

    def get_body(self) -> ft.Control:
        heading = ft.Text(
            "היסטוריית שיחות",
            size=TextSizes.H1,
            weight=ft.FontWeight.BOLD,
            color=ThemeColors.TEXT_MAIN,
            rtl=True,
            text_align=ft.TextAlign.RIGHT,
        )
        # The scrolling thread list (cards fill width via the ListView); expand=True
        # bounds it inside the card.
        self._feed_list = ft.ListView(
            expand=True,
            spacing=UIConstants.ELEMENT_SPACING,
            padding=ft.Padding(0, 8, 0, 8),
        )
        return ft.Column(
            controls=[heading, self._feed_list],
            expand=True,
            spacing=CONTENT_BODY_SPACING,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def get_actions(self) -> list[ft.Control]:
        return [back_to_menu_button(self.page)]   # shared helper; UNWIND to /menu

    def get_status_banner(self) -> ft.Control:
        self._status_text = ft.Text(
            value="",
            size=TextSizes.INPUT,
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.W_600,
            rtl=True,
            text_align=ft.TextAlign.RIGHT,
        )
        self._status_banner = ft.Container(
            content=self._status_text,
            bgcolor=ThemeColors.DANGER,
            padding=14,
            border_radius=UIConstants.CORNER_RADIUS,
            visible=False,
            alignment=ft.Alignment(0, 0),
        )
        return self._status_banner

    def on_mount(self) -> None:
        """Mounted into the page tree: start the owned one-shot thread load.
        Cancelled by BaseView.on_unmount when this view is popped/unmounted."""
        self._load_task = self.page.run_task(self._load)

    # ============================================================
    #  Lifecycle — load threads
    # ============================================================

    async def _load(self) -> None:
        # ---- Identity check: missing → bounce to login immediately ----
        current = self.page.session.store.get(self.SESSION_USER_ID_KEY)
        if not current:
            await self._show_status("אנא התחבר/י תחילה.", ok=False)
            await asyncio.sleep(1.5)
            self._safe_go("/auth/login")
            return

        # ---- Assemble threads off the UI thread (one hop, all DB work) ----
        loading.show_loading(self.page)
        try:
            threads = await asyncio.to_thread(self._assemble_threads, current)
        except Exception:
            loading.hide_loading(self.page)
            log.exception("Matches: load failed user=%s", current)
            await self._show_status(
                "טעינת השיחות נכשלה. אנא נסה/י שוב מאוחר יותר.", ok=False,
            )
            return
        loading.hide_loading(self.page)
        # Route Liveness Check — complements the _closing flag: abort if this
        # view is no longer the active route after the awaited fetch (catches
        # navigations that bypass _on_back, e.g. system back / router redirect).
        if self._closing or not self._is_live():
            return

        # ---- Empty state is a state, not an error ----
        if not threads:
            await self._show_status(
                "עדיין אין שיחות. התחילו שיחה ממסך הגילוי 🙂", ok=False,
            )
            self._feed_list.controls = []
            self._safe_update()
            return

        # Build each row in isolation so one malformed thread is skipped (logged)
        # rather than aborting the whole list behind a dismissed spinner.
        rows: list[ft.Control] = []
        for t in threads:
            try:
                rows.append(self._thread_row(current, t))
            except Exception:  # noqa: BLE001 — one bad row must not kill the list
                log.exception("Matches: failed to build thread row; skipping")
        self._feed_list.controls = rows
        self._safe_update()

    def _assemble_threads(self, user_id: str) -> list[dict]:
        """Blocking: combine conversations + unread counts + peer names.

        Runs entirely inside one `asyncio.to_thread` hop. Uses BOTH injected
        interfaces — messaging for the thread list/badges, profiles for names.
        """
        conversations = self.messaging.get_conversations(user_id)
        unread = self.messaging.get_unread_counts(user_id)
        threads: list[dict] = []
        for conv in conversations:
            # Defensive dict access on the externally-sourced conversation row:
            # a row with no resolvable peer_id is skipped, and every other field
            # falls back to a safe value rather than raising a KeyError that
            # would collapse the entire list into the error banner.
            peer_id = conv.get("peer_id")
            if not peer_id:
                continue
            profile = self.profiles.get_profile(peer_id)   # fail-soft → None
            name = (profile.display_name.for_gender(profile.gender)
                    if profile is not None else "משתמש/ת")
            try:
                unread_count = int(unread.get(peer_id, 0))
            except (TypeError, ValueError):
                unread_count = 0
            threads.append({
                "peer_id":        peer_id,
                "name":           name or "משתמש/ת",
                "last_content":   conv.get("last_content"),
                "last_msg_type":  conv.get("last_msg_type"),
                "last_sender_id": conv.get("last_sender_id"),
                "unread":         unread_count,
            })
        return threads

    # ============================================================
    #  Thread row
    # ============================================================

    def _thread_row(self, self_id: str, t: dict) -> ft.Control:
        avatar = self._avatar(t["name"])

        # Details fill the space between avatar (right) and badge (left); STRETCH
        # + text_align=RIGHT pins the two lines to the right, beside the avatar.
        details = ft.Column(
            controls=[
                ft.Text(
                    t["name"],
                    size=TextSizes.INPUT,
                    weight=ft.FontWeight.BOLD,
                    color=ThemeColors.TEXT_MAIN,
                    rtl=True,
                    text_align=ft.TextAlign.RIGHT,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    self._preview(self_id, t),
                    size=TextSizes.BODY,
                    color=ThemeColors.SECONDARY,
                    rtl=True,
                    text_align=ft.TextAlign.RIGHT,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
            spacing=2,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            alignment=ft.MainAxisAlignment.CENTER,
        )

        # RTL-native order: first child = rightmost. So [avatar, details, badge]
        # → avatar FAR RIGHT, details fill the middle, badge FAR LEFT.
        controls: list[ft.Control] = [avatar, details]
        if t["unread"] > 0:
            controls.append(self._badge(t["unread"]))

        row = ft.Row(
            controls=controls,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        )

        # Full-width card (fills the ListView) so it never floats left.
        return ft.Container(
            content=row,
            height=self._CARD_HEIGHT,
            bgcolor=ThemeColors.SURFACE,
            border_radius=UIConstants.CORNER_RADIUS,
            padding=ft.Padding(16, 8, 16, 8),
            ink=True,
            on_click=lambda _e, pid=t["peer_id"]: self._open_chat(pid),
        )

    def _avatar(self, name: str) -> ft.Control:
        """Initials circle (brand red) — simple, high-contrast, senior-readable."""
        initial = (name.strip()[:1] or "?")
        return ft.Container(
            width=self._AVATAR_DIAMETER,
            height=self._AVATAR_DIAMETER,
            border_radius=self._AVATAR_DIAMETER / 2,
            bgcolor=ThemeColors.PRIMARY,
            alignment=ft.Alignment(0, 0),
            content=ft.Text(
                initial,
                size=TextSizes.H2,
                weight=ft.FontWeight.BOLD,
                color=ThemeColors.TEXT_ON_PRIMARY,
            ),
        )

    def _badge(self, count: int) -> ft.Control:
        """Unread-count badge — a red circle with the number, on the far left."""
        return ft.Container(
            width=self._BADGE_DIAMETER,
            height=self._BADGE_DIAMETER,
            border_radius=self._BADGE_DIAMETER / 2,
            bgcolor=ThemeColors.DANGER,
            alignment=ft.Alignment(0, 0),
            content=ft.Text(
                str(count),
                size=TextSizes.BODY,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.WHITE,
            ),
        )

    def _preview(self, self_id: str, t: dict) -> str:
        """One-line preview of the last message, with a 'you:' hint and a
        friendly placeholder for non-text messages."""
        msg_type = t["last_msg_type"]
        if msg_type == "AUDIO":
            body = "🎤 הודעה קולית"
        elif msg_type == "IMAGE":
            body = "📷 תמונה"
        else:
            body = (t["last_content"] or "").strip()
            if len(body) > self._PREVIEW_MAX_CHARS:
                body = body[: self._PREVIEW_MAX_CHARS] + "…"
        prefix = "את/ה: " if t["last_sender_id"] == self_id else ""
        return prefix + body

    # ============================================================
    #  Interaction
    # ============================================================

    def _open_chat(self, peer_id: str) -> None:
        # Stash the chosen peer (same mechanism DiscoverView uses), then route
        # to the chat screen, which reads `selected_peer_id` as its peer_id.
        self._closing = True
        self.page.session.store.set(self.SELECTED_PEER_ID_KEY, peer_id)
        self.page.go(self._CHAT_ROUTE)

    # ============================================================
    #  Helpers
    # ============================================================

    def _safe_go(self, route: str) -> None:
        if not self._closing:
            self._closing = True
            self.page.go(route)

    def _safe_update(self) -> None:
        if self._closing:
            return
        try:
            self.page.update()
        except Exception:  # noqa: BLE001 — stale view after navigation
            pass

    async def _show_status(self, message: str, *, ok: bool) -> None:
        self._status_text.value = message
        self._status_banner.bgcolor = (
            ThemeColors.SUCCESS if ok else ThemeColors.DANGER
        )
        self._status_banner.visible = True
        try:
            self._status_banner.update()
        except Exception:  # noqa: BLE001
            pass
