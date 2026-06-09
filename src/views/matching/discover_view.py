"""Discover — browse other members and open a quick profile preview.

Architecture
------------
Depends on a single role-interface, `IProfileRepository`, per the project's
Interface Segregation rule. It needs to *read candidate profiles* — nothing
more — so it never sees `IAuthService` or `IMessagingService`. The router
builds it like so::

    def _build_discover(self) -> ft.View:
        profiles = cast(IProfileRepository,
                        self.page.session.store.get("profiles"))
        return DiscoverView(self.page, profiles).build()

Like every user-scoped screen, it reads `current_user_id` from
`page.session.store` (written by `login_view` on success). If that token is
missing or orphaned, it refuses to load data, shows the Hebrew banner
"אנא התחבר/י תחילה", and bounces to `/auth/login`.

UX
--
Senior-first and structurally IDENTICAL to MyProfileView: a full-screen 'BG'
background with the shared 50%-white translucent card (same width / margin /
padding), a scrolling Title + profile list inside it, and a sticky "back"
button below. Cards are anchored to the RIGHT — avatar on the far right, the
name + details tightly to its left and fully right-aligned. Tapping a member
opens an RTL selection sheet (view profile / start chat).
"""
from __future__ import annotations
import functools
import logging

import flet as ft

from views._base import BaseView
from views.common.helpers.navigation import back_to_menu_button
from components.typography import create_screen_heading
from views.common.helpers.safe_list import build_items_safe
from views.common.helpers.load_flow import run_guarded_load, LoadGuard
from components.buttons import create_primary_button, create_secondary_button
from components.feedback import create_status_banner, show_status
from components.avatars import create_initial_avatar
from components.cards import create_member_row_card
from services.interfaces.i_profile_repository import IProfileRepository
from models.user_profile import UserProfile, Gender, AccountStatus
from style.design_system import DS
from utils.constants import MatchConfig
from utils.session_keys import CURRENT_USER_ID, SELECTED_PEER_ID
from utils import routes

log = logging.getLogger(__name__)

_CARD_HEIGHT: int = DS.sizing.tile_h
_AVATAR_DIAMETER: int = DS.sizing.avatar_sm


class DiscoverView(BaseView):
    ROUTE = routes.DISCOVER

    # Identity token written by login_view on success; read here. Alias of the
    # canonical `utils.session_keys.CURRENT_USER_ID` constant.
    SESSION_USER_ID_KEY = CURRENT_USER_ID

    # Set when the user picks a candidate, so the (placeholder) destination
    # screens can later load the right person. Written here; read by the future
    # "view profile" / "chat" screens. Alias of the canonical
    # `utils.session_keys.SELECTED_PEER_ID` constant.
    SELECTED_PEER_ID_KEY = SELECTED_PEER_ID

    # Placeholder routes the two selection actions navigate to.
    _VIEW_PROFILE_ROUTE = routes.PEER_PROFILE   # view another member's profile
    _CHAT_ROUTE         = routes.CHAT_NEW       # start a chat with them

    def __init__(self, page: ft.Page, profile_repo: IProfileRepository) -> None:
        super().__init__(page)
        self.profile_repo = profile_repo
        # Candidates hydrated on mount; kept so the bottom-sheet preview can
        # read full fields without a second backend round-trip.
        self._candidates: list[UserProfile] = []
        # Re-entrancy guard for the selection sheet — see `_on_candidate_tap`.
        self._sheet_open = False

    # ============================================================
    #  Layout
    # ============================================================

    def get_header(self):
        return create_screen_heading("אנשים שתרצו להכיר")

    def get_content(self) -> list[ft.Control]:
        # HUB centered card: the feed Column is populated at runtime; the status
        # banner handles auth/empty/error states inline.
        self._feed_column = ft.Column(
            controls=[],
            spacing=DS.spacing.element,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self._status_banner, self._status_text = create_status_banner()
        return [self._feed_column, self._status_banner]

    def get_actions(self) -> list[ft.Control]:
        return [back_to_menu_button(self.page)]

    def on_mount(self) -> None:
        """Mounted into the page tree: start the owned one-shot feed load.
        Cancelled by BaseView.on_unmount when this view is popped/unmounted."""
        self._load_task = self.page.run_task(self._load_candidates)

    # ============================================================
    #  Lifecycle — load the feed
    # ============================================================

    async def _load_candidates(self) -> None:
        # Identity read kept explicit at the call site so the auth contract is
        # visible; the guard/spinner/liveness scaffolding lives in the shared
        # run_guarded_load (views/common/load_flow.py).
        current_user_id = self.page.session.store.get(self.SESSION_USER_ID_KEY)

        async def _render(candidates: list[UserProfile]) -> None:
            # Empty feed is a state, not an error.
            self._candidates = candidates
            if not candidates:
                await show_status(self._status_banner, self._status_text,
                    "עדיין אין פרופילים להצגה. חזרו מאוחר יותר 🙂", ok=False,
                )
                self._feed_column.controls = []
                self.page.update()
                return
            # Build each tile in isolation so one malformed candidate is SKIPPED
            # with a log line rather than blanking the whole feed (Peer Layout
            # Boundary Rule §4; see views/common/safe_list.py).
            self._feed_column.controls = build_items_safe(
                candidates,
                self._candidate_tile,
                logger=log,
                error_message="Discover: failed to build candidate tile; skipping",
            )
            self.page.update()

        await run_guarded_load(
            self.page,
            guards=[LoadGuard(
                ok=bool(current_user_id),
                message="אנא התחבר/י תחילה",
                # Don't yank a viewer who already left during the banner.
                bounce=lambda: self._is_live() and self.page.go(routes.LOGIN),
            )],
            fetch=lambda: self.profile_repo.discover_profiles(
                current_user_id, MatchConfig.DISCOVER_PAGE_SIZE,
            ),
            on_success=_render,
            is_stale=lambda: not self._is_live(),
            status_banner=self._status_banner,
            status_text=self._status_text,
            logger=log,
            fetch_error_message="טעינת האנשים נכשלה. אנא נסה/י שוב מאוחר יותר.",
            fetch_error_log=f"Discover: feed load failed for viewer={current_user_id}",
        )

    # ============================================================
    #  Candidate tile
    # ============================================================

    def _candidate_tile(self, profile: UserProfile) -> ft.Control:
        """A single tappable member row — name, meta line, presence dot."""
        name = profile.display_name.for_gender(profile.gender) or ""
        online = profile.status is AccountStatus.ACTIVE
        return create_member_row_card(
            create_initial_avatar(name, diameter=_AVATAR_DIAMETER, online=online),
            name,
            self._meta_line(profile),
            on_click=lambda _e, p=profile: self._on_candidate_tap(p),
            height=_CARD_HEIGHT,
        )

    # ============================================================
    #  Selection action sheet (tap a candidate → choose an action)
    # ============================================================

    def _on_candidate_tap(self, profile: UserProfile) -> None:
        """Tapping a candidate opens a senior-friendly selection sheet offering
        the two large action choices: view their profile, or start a chat.

        Guarded against re-entrancy: a senior user often taps a row again
        before the sheet has visibly appeared. Without this guard each tap
        builds and shows its OWN `BottomSheet`, stacking them on the dialog
        stack. One sheet at a time; `on_dismiss` is the single place that
        clears the flag — NOT `_close_sheet`, which only calls `pop_dialog()`
        and does not await the dismiss animation."""
        if self._sheet_open:
            return
        self._sheet_open = True
        sheet = self._build_action_sheet(profile)
        sheet.on_dismiss = lambda _e: setattr(self, "_sheet_open", False)
        self.page.show_dialog(sheet)              # Flet 0.84 DialogControl API

    def _build_action_sheet(self, profile: UserProfile) -> ft.BottomSheet:
        """RTL bottom sheet: WHO was tapped + exactly two large PRIMARY action
        buttons (view profile / start chat), plus a neutral Close.

        The action labels are long, so the buttons drop to DS.type.input
        (25px) — still senior-readable — to sit cleanly on the full-width button
        while staying high-contrast brand-red.
        """
        name = profile.display_name.for_gender(profile.gender) or ""
        sheet = ft.BottomSheet(content=ft.Container(), scrollable=True) # filled below

        # ---- Who: name + meta line so the senior knows whom they picked ----
        title = ft.Text(
            name,
            size=DS.type.h2,
            weight=ft.FontWeight.BOLD,
            color=DS.palette.text_main,
            rtl=True,
            text_align=ft.TextAlign.CENTER,
        )
        subtitle = ft.Text(
            self._meta_line(profile),
            size=DS.type.input,
            color=DS.palette.secondary,
            rtl=True,
            text_align=ft.TextAlign.CENTER,
        )
        prompt = ft.Text(
            "מה תרצו לעשות?",
            size=DS.type.input,
            weight=ft.FontWeight.W_600,
            color=DS.palette.text_main,
            rtl=True,
            text_align=ft.TextAlign.CENTER,
        )

        # ---- Exactly two distinct, large action buttons ----
        view_button = create_primary_button(
            "צפייה בפרופיל שלו / שלה",
            functools.partial(self._on_action_chosen, sheet, self._VIEW_PROFILE_ROUTE, profile),
            text_size=DS.type.input,
        )
        chat_button = create_primary_button(
            "התחל שיחה / שלח הודעה",
            functools.partial(self._on_action_chosen, sheet, self._CHAT_ROUTE, profile),
            text_size=DS.type.input,
        )
        # Neutral dismiss — secondary (blue-grey), never the brand red.
        close_button = create_secondary_button(
            "סגירה", lambda _e: self._close_sheet(),
        )

        sheet.content = ft.Container(
            padding=DS.pad.section,
            bgcolor=DS.palette.surface,
            content=ft.Column(
                controls=[
                    title,
                    subtitle,
                    prompt,
                    view_button,
                    chat_button,
                    close_button,
                ],
                tight=True,
                spacing=DS.spacing.body,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        return sheet

    async def _on_action_chosen(
        self, sheet: ft.BottomSheet, route: str, profile: UserProfile,
        _e: ft.ControlEvent | None = None,
    ) -> None:
        """Remember the picked peer, dismiss the sheet, then navigate.

        The peer id is stashed in `session.store` under SELECTED_PEER_ID_KEY so
        the destination screens can load the right person — mirroring how login
        stashes the UID before routing.

        `await push_route()` (not `page.go()`) is required here. In Flet 0.84,
        `page.go()` is deprecated and implemented as
        `asyncio.create_task(push_route(...))` — it only schedules the route
        push for a later event-loop tick. When called immediately after
        `pop_dialog()` (a sync patch to Flutter), the two async operations race
        and the route push is silently dropped on the first attempt."""
        self.page.session.store.set(self.SELECTED_PEER_ID_KEY, profile.user_id)
        self._close_sheet()
        await self.page.push_route(route)

    def _close_sheet(self) -> None:
        self._sheet_open = False        # reset eagerly; on_dismiss covers scrim-tap
        self.page.pop_dialog()          # Flet 0.84 DialogControl API

    # ============================================================
    #  Helpers
    # ============================================================

    @staticmethod
    def _age_word(gender: Gender) -> str:
        """Gender-correct Hebrew age prefix (בן / בת)."""
        if gender is Gender.MALE:
            return "בן"
        if gender is Gender.FEMALE:
            return "בת"
        return "בן/בת"

    def _meta_line(self, profile: UserProfile) -> str:
        """'בן 67 · חיפה' — age (when real) and city, gender-aware.

        `date_of_birth` is seeded with the 1900-01-01 sentinel until onboarding
        fills it in, so we only show an age once it's a real birth date.
        """
        parts: list[str] = []
        try:
            if profile.date_of_birth and profile.date_of_birth.year > 1900:
                parts.append(f"{self._age_word(profile.gender)} {profile.age}")
        except Exception:  # noqa: BLE001 — a bad DOB must not break the feed row
            pass
        # Defensive: never assume location.city is a populated string.
        city = (getattr(profile.location, "city", "") or "").strip()
        if city:
            parts.append(city)
        return "  ·  ".join(parts) if parts else "חבר/ה חדש/ה"
