"""ChatView — one-on-one direct messaging. Proof of Interface Segregation.

This file imports NEITHER IAuthService, IProfileRepository, SQLiteBackEndService,
nor sqlite3 — it depends on the single capability it uses: `IMessagingService`
(send + read chat messages). A future swap to a real-time provider replaces the
backend without touching this view.

UX (50+ audience)
-----------------
Built from the SAME shell as every other screen: the shared full-screen 'BG'
background (BoxFit.FILL) + a 50%-white `translucent_card` (via `background_screen`
/ `translucent_card`) that holds an H1 heading and the scrolling message list,
with a sticky bottom action bar carrying the send bar (Hebrew text field on the
right, "שלח" on the left) and a SECONDARY (blue-grey) "חזור" button — navigation
colour per the design system, distinct from the red PRIMARY send action.

Bubble side is set with ABSOLUTE container alignment (x = +1 mine / -1 peer),
which is immune to the RTL main-axis flip that bites CrossAxisAlignment-based
layouts in this Flet build. That alignment logic is preserved verbatim through
the shell redesign — mine right, peer left.
"""
from __future__ import annotations
import asyncio
import logging

import flet as ft

from views._base import BaseView
from views.common.screen import BodyLayout
from views.common import renderer as ui
from views.common.navigation import go_back
from views.common.render import build_items_safe
from views.common.load_flow import run_guarded_load, LoadGuard
from components.inputs import create_hebrew_text_field
from components.dividers import create_action_divider
from components.feedback import create_status_banner, show_status
from components.chat import create_chat_bubble
from services.i_messaging_service import IMessagingService
from style.design_system import DS
from utils.constants import MessageType, ChatConfig

log = logging.getLogger(__name__)


class ChatView(BaseView):
    """One-on-one chat between `self_id` and `peer_id`.

    Depends ONLY on `IMessagingService` — the UI is decoupled from auth and raw
    DB access. The router injects the dependency and both identities.
    """

    ROUTE = "/chat/new"

    # Written by login_view / boot; read here to validate that the injected
    # `self_id` really is the logged-in user.
    SESSION_USER_ID_KEY = "current_user_id"

    # Where "back" returns to (the Discover feed the chat was opened from).
    _DISCOVER_ROUTE = "/matching/discover"

    def __init__(
        self,
        page: ft.Page,
        messaging: IMessagingService,
        self_id: str,
        peer_id: str,
    ) -> None:
        super().__init__(page)
        self.messaging = messaging
        self.self_id = self_id
        self.peer_id = peer_id
        # Set when we navigate away, so any in-flight async task stops touching
        # the (replaced) page — prevents stale updates / leaked references.
        self._closing: bool = False

    # ============================================================
    #  Layout
    # ============================================================

    BODY_LAYOUT = BodyLayout.SELF_SCROLLING   # the ListView owns its own scroll

    def get_header(self) -> ui.UIComponent:
        # ChatView depends ONLY on IMessagingService (Interface Segregation), so it
        # can't resolve the peer's name without widening the contract — the title
        # is a generic, senior-readable "שיחה".
        return ui.heading("שיחה")

    def get_content(self) -> list[ui.UIComponent]:
        # The message list is mutated at runtime, so it is PRE-BUILT and embedded
        # via raw(); the engine STRETCHes the body so each bubble's wrapper spans
        # the full width (the absolute-alignment bubble logic relies on it).
        self._messages_list = ft.ListView(
            expand=True,
            spacing=DS.spacing.bar,
            auto_scroll=True,
            padding=DS.pad.list_v,
        )
        return [ui.raw(self._messages_list)]

    def get_actions(self) -> list[ui.UIComponent]:
        # Send bar (field RIGHT, "שלח" LEFT), a divider, then a SECONDARY stack-
        # aware back button. The engine stretches the send bar to full width
        # (composer expands) and auto-centres the fixed-width back button.
        self._composer = create_hebrew_text_field(
            "הקלידו הודעה…", hebrew_content=True, on_submit=self._on_send,
        )
        self._composer.expand = True                 # fill the bar (minus button)
        self._composer.width = None
        send_bar = ui.row(
            [ui.raw(self._composer),
             ui.primary_button("שלח", self._on_send, width=DS.sizing.send_btn_w)],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=DS.spacing.md,
        )
        return [
            send_bar,
            ui.raw(create_action_divider(height=DS.sizing.divider_h)),
            ui.secondary_button("חזור", self._on_back),
        ]

    def get_status_banner(self) -> ui.UIComponent:
        self._status_banner, self._status_text = create_status_banner()
        return ui.raw(self._status_banner)

    def on_mount(self) -> None:
        """Mounted into the page tree: start the owned one-shot history load
        (no background polling → nothing leaks). Cancelled by BaseView.on_unmount
        when this view is popped/unmounted."""
        self._load_task = self.page.run_task(self._load_history)

    # ============================================================
    #  Lifecycle — load history, validate identity
    # ============================================================

    async def _load_history(self) -> None:
        # Identity integrity: the injected self_id MUST match the logged-in user,
        # and a peer must be selected. Both are precondition guards for the shared
        # run_guarded_load (views/common/load_flow.py); the liveness predicate is
        # this view's _closing flag.
        current = self.page.session.store.get(self.SESSION_USER_ID_KEY)
        identity_ok = bool(current) and bool(self.self_id) and current == self.self_id

        async def _on_loaded(msgs: list[dict]) -> None:
            self._render(msgs)
            # Mark the peer's messages to me as READ (best-effort).
            try:
                await asyncio.to_thread(
                    self.messaging.mark_messages_as_read,
                    self.self_id, self.peer_id,
                )
            except Exception:  # noqa: BLE001 — non-critical
                log.warning("Chat: mark-as-read failed", exc_info=True)

        await run_guarded_load(
            self.page,
            guards=[
                LoadGuard(
                    ok=identity_ok,
                    message="אירעה שגיאת זיהוי. אנא התחבר/י מחדש.",
                    bounce=lambda: self._safe_go("/auth/login"),
                ),
                LoadGuard(
                    ok=bool(self.peer_id),
                    message="לא נבחר/ה משתמש/ת לשיחה.",
                    bounce=lambda: self._safe_go(self._DISCOVER_ROUTE),
                ),
            ],
            # Newest page (no cursor); back-paging would pass the oldest loaded
            # message's created_at as the cursor.
            fetch=lambda: self.messaging.get_chat_history(
                self.self_id, self.peer_id, ChatConfig.DEFAULT_PAGE_SIZE,
            ),
            on_success=_on_loaded,
            is_stale=lambda: self._closing,
            status_banner=self._status_banner,
            status_text=self._status_text,
            logger=log,
            fetch_error_message="טעינת השיחה נכשלה. אנא נסה/י שוב.",
            fetch_error_log=(
                f"Chat: history load failed self={self.self_id} peer={self.peer_id}"
            ),
        )

    async def _reload_messages(self) -> None:
        """Re-fetch + re-render the history without the full-screen spinner
        (used right after sending, for a snappy feel)."""
        try:
            msgs = await asyncio.to_thread(
                self.messaging.get_chat_history,
                self.self_id, self.peer_id,
                ChatConfig.DEFAULT_PAGE_SIZE,
            )
        except Exception:
            log.exception("Chat: reload failed self=%s peer=%s",
                          self.self_id, self.peer_id)
            return
        if self._closing:
            return
        self._render(msgs)

    def _render(self, msgs: list[dict]) -> None:
        # Build each bubble in isolation: a single malformed message dict
        # (missing/renamed key, a NULL content on a non-text message) is skipped
        # with a log line rather than aborting the whole render and leaving the
        # chat stuck behind a dismissed spinner (shared render-seam helper;
        # see views/common/render.py).
        self._messages_list.controls = build_items_safe(
            msgs,
            self._bubble,
            logger=log,
            error_message="Chat: failed to build bubble; skipping",
        )
        self._safe_update()

    # ============================================================
    #  Send handler
    # ============================================================

    async def _on_send(self, e: ft.ControlEvent) -> None:
        text = (self._composer.value or "").strip()
        if not text:
            return
        # Optimistic clear so the senior sees the field empty immediately.
        self._composer.value = ""
        self._safe_update()
        try:
            await asyncio.to_thread(
                self.messaging.send_direct_message,
                self.self_id, self.peer_id, text, MessageType.TEXT,
            )
        except Exception:
            log.exception("Chat: send failed self=%s peer=%s",
                          self.self_id, self.peer_id)
            await show_status(self._status_banner, self._status_text,"שליחת ההודעה נכשלה. אנא נסה/י שוב.", ok=False)
            return
        await self._reload_messages()

    # ============================================================
    #  Bubble + helpers
    # ============================================================

    def _bubble(self, m: dict) -> ft.Control:
        """A single chat bubble — the styling + RTL-immune side-anchoring lives
        in `create_chat_bubble`; this method only reads the message dict.

        Defensive dict access: never assume the message dict's shape. A missing
        sender_id degrades to a peer bubble; a missing/NULL/non-str content
        (e.g. an AUDIO/IMAGE row whose content is a reference, or junk) degrades
        to an empty string — `ft.Text(None)` would otherwise be a render-time risk.
        """
        mine = m.get("sender_id") == self.self_id
        content = m.get("content")
        content = content if isinstance(content, str) else ""
        return create_chat_bubble(content, mine=mine)

    def _on_back(self, e: ft.ControlEvent) -> None:
        # Mark closing FIRST so any in-flight task skips its page updates, then
        # pop ONE level off the stack. Chat can be opened from Discover OR from
        # Matches, so a stack-aware pop returns to whichever screen opened it —
        # a hard-coded /matching/discover would strand a user who came from
        # Matches. Falls back to Discover only if chat is somehow the root view.
        self._closing = True
        go_back(self.page, fallback=self._DISCOVER_ROUTE)

    def _safe_go(self, route: str) -> None:
        if not self._closing:
            self._closing = True
            self.page.go(route)

    def _safe_update(self) -> None:
        """page.update() guarded against a view that's already navigated away."""
        if self._closing:
            return
        try:
            self.page.update()
        except Exception:  # noqa: BLE001 — stale view after navigation
            pass
