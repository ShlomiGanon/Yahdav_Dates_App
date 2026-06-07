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
import logging

import flet as ft

from views._base import BaseView
from views.common.screen import BodyLayout
from views.common import renderer as ui
from views.common.navigation import back_to_menu_button
from views.common.render import build_items_safe
from views.common.load_flow import run_guarded_load, LoadGuard
from components.feedback import create_status_banner, show_status
from style.design_system import DS
from components.avatars import create_initial_avatar, create_unread_badge
from components.cards import create_tile_card
from services.i_messaging_service import IMessagingService
from services.i_profile_repository import IProfileRepository
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

    _CARD_HEIGHT: int = DS.sizing.tile_h   # 86px row
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

    def get_header(self) -> ui.UIComponent:
        return ui.heading("היסטוריית שיחות")

    def get_content(self) -> list[ui.UIComponent]:
        # The scrolling thread list is populated at runtime (_load), so it is
        # PRE-BUILT and embedded via raw(); the engine expands the body (the
        # ListView owns its scroll — SELF_SCROLLING).
        self._feed_list = ft.ListView(
            expand=True,
            spacing=DS.spacing.element,
            padding=DS.pad.list_v,
        )
        return [ui.raw(self._feed_list)]

    def get_actions(self) -> list[ui.UIComponent]:
        return [ui.raw(back_to_menu_button(self.page))]   # UNWIND to /menu

    def get_status_banner(self) -> ui.UIComponent:
        self._status_banner, self._status_text = create_status_banner()
        return ui.raw(self._status_banner)

    def on_mount(self) -> None:
        """Mounted into the page tree: start the owned one-shot thread load.
        Cancelled by BaseView.on_unmount when this view is popped/unmounted."""
        self._load_task = self.page.run_task(self._load)

    # ============================================================
    #  Lifecycle — load threads
    # ============================================================

    async def _load(self) -> None:
        # Identity read kept explicit; the guard/spinner/liveness scaffolding is
        # the shared run_guarded_load (views/common/load_flow.py). The liveness
        # predicate folds in this view's _closing flag so a fetch that resolves
        # after navigate-away (system back / router redirect) is dropped.
        current = self.page.session.store.get(self.SESSION_USER_ID_KEY)

        async def _render(threads: list[dict]) -> None:
            # Empty state is a state, not an error.
            if not threads:
                await show_status(self._status_banner, self._status_text,
                    "עדיין אין שיחות. התחילו שיחה ממסך הגילוי 🙂", ok=False,
                )
                self._feed_list.controls = []
                self._safe_update()
                return
            # One malformed thread is skipped (logged), never aborting the list.
            self._feed_list.controls = build_items_safe(
                threads,
                lambda t: self._thread_row(current, t),
                logger=log,
                error_message="Matches: failed to build thread row; skipping",
            )
            self._safe_update()

        await run_guarded_load(
            self.page,
            guards=[LoadGuard(
                ok=bool(current),
                message="אנא התחבר/י תחילה.",
                bounce=lambda: self._safe_go("/auth/login"),
            )],
            fetch=lambda: self._assemble_threads(current),
            on_success=_render,
            is_stale=lambda: self._closing or not self._is_live(),
            status_banner=self._status_banner,
            status_text=self._status_text,
            logger=log,
            fetch_error_message="טעינת השיחות נכשלה. אנא נסה/י שוב מאוחר יותר.",
            fetch_error_log=f"Matches: load failed user={current}",
        )

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
        avatar = create_initial_avatar(t["name"], diameter=DS.sizing.avatar_sm)

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
            spacing=DS.spacing.xxs,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            alignment=ft.MainAxisAlignment.CENTER,
        )

        # RTL-native order: first child = rightmost. So [avatar, details, badge]
        # → avatar FAR RIGHT, details fill the middle, badge FAR LEFT.
        controls: list[ft.Control] = [avatar, details]
        if t["unread"] > 0:
            controls.append(create_unread_badge(t["unread"]))

        row = ft.Row(
            controls=controls,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=DS.spacing.md,
        )

        # Full-width card (fills the ListView) so it never floats left.
        return create_tile_card(
            row,
            height=self._CARD_HEIGHT,
            on_click=lambda _e, pid=t["peer_id"]: self._open_chat(pid),
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
