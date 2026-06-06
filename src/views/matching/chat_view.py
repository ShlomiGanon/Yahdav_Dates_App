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
from views.common.screen import background_screen, translucent_card
from components import loading
from components.buttons import create_primary_button, create_secondary_button
from components.inputs import create_hebrew_text_field
from services.I_Messaging_Service import IMessagingService
from utils.constants import MessageType, ChatConfig, TextSizes, UIConstants, ThemeColors

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

    def build(self) -> ft.View:
        # The layout mirrors the canonical screen shell used by Discover / My
        # Profile / Matches: a `background_screen` wrapping a screen-filling
        # Column of [ scrollable translucent_card , sticky bottom action bar ].

        # ---- H1 heading (every other screen opens with one). ChatView depends
        # ONLY on IMessagingService by Interface Segregation, so it cannot
        # resolve the peer's display name without taking on IProfileRepository —
        # which would widen the contract. The title is therefore a generic,
        # senior-readable "שיחה" rather than the peer's name. ----
        heading = ft.Text(
            "שיחה",
            size=TextSizes.H1,
            weight=ft.FontWeight.BOLD,
            color=ThemeColors.TEXT_MAIN,
            rtl=True,
            text_align=ft.TextAlign.RIGHT,
        )

        # ---- Inline status banner (identity / load / send errors) ----
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

        # ---- The scrolling message list (auto-scrolls to newest) ----
        self._messages_list = ft.ListView(
            expand=True,
            spacing=10,
            auto_scroll=True,
            padding=ft.Padding(0, 8, 0, 8),
        )

        # ---- Scrollable content card — the SAME translucent_card shell as the
        # other screens (50% white, identical margin/padding). The inner Column
        # is STRETCH so the heading right-aligns and, crucially, the message list
        # spans the full card width — the absolute-alignment bubble logic relies
        # on each bubble's wrapper filling that width to anchor right/left. ----
        scroll_region = translucent_card(
            ft.Column(
                controls=[heading, self._status_banner, self._messages_list],
                spacing=14,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            expand=True,
            margin=ft.Margin.only(left=12, top=12, right=12, bottom=8),
            padding=ft.Padding(20, 20, 20, 16),
        )

        # ---- Send bar: text field on the RIGHT, "שלח" button on the LEFT.
        # Under page-RTL the first Row child renders rightmost, so [field, send]
        # puts the (expanding) field on the right and the button on the left.
        # Both are design-system primitives (create_hebrew_text_field /
        # create_primary_button) — no raw Flet controls. ----
        self._composer = create_hebrew_text_field(
            "הקלידו הודעה…", hebrew_content=True, on_submit=self._on_send,
        )
        self._composer.expand = True                 # fill the bar (minus button)
        self._composer.width = None
        send_button = create_primary_button("שלח", self._on_send, width=140)
        send_bar = ft.Row(
            controls=[self._composer, send_button],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        )

        # ---- Divider separating the (primary) compose action from the
        # (secondary) navigation, mirroring MyProfileView's save/back split so a
        # senior never confuses the two. ----
        divider = ft.Container(
            content=ft.Divider(thickness=1, color=ThemeColors.SECONDARY),
            padding=ft.Padding(0, 8, 0, 4),
        )

        # ---- SECONDARY (blue-grey) back button — navigation colour per the
        # action hierarchy (not the red PRIMARY it used to be). It routes through
        # the view's own _on_back so the _closing guard still fires; the shared
        # back_to_menu_button helper would skip that guard. ----
        back_button = create_secondary_button("חזור", self._on_back)

        # ---- Sticky bottom action bar (never scrolls), same transparent bar the
        # other screens use so it floats on the background image. STRETCH lets the
        # send bar span the full width (so the composer can expand); the
        # fixed-width back button is re-centred in its own wrapper. ----
        action_bar = ft.Container(
            bgcolor=ft.Colors.TRANSPARENT,
            padding=ft.Padding(24, 12, 24, 20),
            content=ft.Column(
                controls=[
                    send_bar,
                    divider,
                    ft.Container(content=back_button, alignment=ft.Alignment(0, 0)),
                ],
                tight=True,
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

        view = background_screen(
            self.ROUTE,
            ft.Column(
                controls=[scroll_region, action_bar],
                expand=True,
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        # One-shot history load on mount (no background polling → nothing leaks).
        try:
            self.page.run_task(self._load_history)
        except AttributeError:
            asyncio.create_task(self._load_history())

        return view

    # ============================================================
    #  Lifecycle — load history, validate identity
    # ============================================================

    async def _load_history(self) -> None:
        # ---- Identity integrity: the injected self_id MUST match the logged-in
        # user. Missing/mismatched ⇒ banner + bounce to login. ----
        current = self.page.session.store.get(self.SESSION_USER_ID_KEY)
        if not current or not self.self_id or current != self.self_id:
            await self._show_status("אירעה שגיאת זיהוי. אנא התחבר/י מחדש.", ok=False)
            await asyncio.sleep(1.5)
            self._safe_go("/auth/login")
            return
        if not self.peer_id:
            await self._show_status("לא נבחר/ה משתמש/ת לשיחה.", ok=False)
            await asyncio.sleep(1.5)
            self._safe_go(self._DISCOVER_ROUTE)
            return

        # ---- Fetch the page of history off the UI thread ----
        loading.show_loading(self.page)
        try:
            # Newest page (no cursor); back-paging would pass the oldest loaded
            # message's created_at as the cursor.
            msgs = await asyncio.to_thread(
                self.messaging.get_chat_history,
                self.self_id, self.peer_id,
                ChatConfig.DEFAULT_PAGE_SIZE,
            )
        except Exception:
            loading.hide_loading(self.page)
            log.exception("Chat: history load failed self=%s peer=%s",
                          self.self_id, self.peer_id)
            await self._show_status("טעינת השיחה נכשלה. אנא נסה/י שוב.", ok=False)
            return
        loading.hide_loading(self.page)
        if self._closing:
            return

        self._render(msgs)

        # ---- Mark the peer's messages to me as READ (best-effort) ----
        try:
            await asyncio.to_thread(
                self.messaging.mark_messages_as_read, self.self_id, self.peer_id,
            )
        except Exception:  # noqa: BLE001 — non-critical
            log.warning("Chat: mark-as-read failed", exc_info=True)

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
        # chat stuck behind a dismissed spinner.
        bubbles: list[ft.Control] = []
        for m in msgs:
            try:
                bubbles.append(self._bubble(m))
            except Exception:  # noqa: BLE001 — one bad message must not kill the thread
                log.exception("Chat: failed to build bubble; skipping")
        self._messages_list.controls = bubbles
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
            await self._show_status("שליחת ההודעה נכשלה. אנא נסה/י שוב.", ok=False)
            return
        await self._reload_messages()

    # ============================================================
    #  Bubble + helpers
    # ============================================================

    def _bubble(self, m: dict) -> ft.Control:
        """A single chat bubble, side-anchored by ABSOLUTE alignment.

        The wrapper Container fills the list width; `ft.Alignment(±1, 0)` then
        pins the content-sized bubble to the right (mine) or left (peer) — an
        absolute coordinate, so it is unaffected by the RTL flip.
        """
        # Defensive dict access: never assume the message dict's shape. A
        # missing sender_id degrades to a peer bubble; a missing/NULL/non-str
        # content (e.g. an AUDIO/IMAGE row whose content is a reference, or junk)
        # degrades to an empty string — `ft.Text(None)` would otherwise be a
        # render-time risk.
        mine = m.get("sender_id") == self.self_id
        content = m.get("content")
        content = content if isinstance(content, str) else ""
        bubble = ft.Container(
            content=ft.Text(
                content,
                size=TextSizes.INPUT,
                color=ThemeColors.TEXT_MAIN,
                rtl=True,
                text_align=ft.TextAlign.RIGHT,
                selectable=True,
            ),
            padding=12,
            border_radius=16,
            bgcolor=ThemeColors.BUBBLE_SELF if mine else ThemeColors.BUBBLE_PEER,
        )
        return ft.Container(
            content=bubble,
            alignment=ft.Alignment(1, 0) if mine else ft.Alignment(-1, 0),
        )

    def _on_back(self, e: ft.ControlEvent) -> None:
        # Mark closing FIRST so any in-flight task skips its page updates.
        self._closing = True
        self.page.go(self._DISCOVER_ROUTE)

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
