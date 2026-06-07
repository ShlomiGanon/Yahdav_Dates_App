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
import asyncio
import logging

import flet as ft

from views._base import BaseView
from views.common.screen import CONTENT_BODY_SPACING
from views.common.navigation import back_to_menu_button
from components import loading
from components.buttons import create_primary_button, create_secondary_button
from components.typography import create_screen_heading
from components.feedback import create_status_banner, show_status
from components.discover import create_candidate_tile
from services.I_Profile_Repository import IProfileRepository
from models.user_profile import UserProfile, Gender, AccountStatus
from utils.constants import TextSizes, UIConstants, ThemeColors, MatchConfig

log = logging.getLogger(__name__)


class DiscoverView(BaseView):
    ROUTE = "/matching/discover"

    # Identity token written by login_view on success; read here. Centralised
    # so a typo can't silently desync writer and reader.
    SESSION_USER_ID_KEY = "current_user_id"

    # Set when the user picks a candidate, so the (placeholder) destination
    # screens can later load the right person. Written here; read by the future
    # "view profile" / "chat" screens.
    SELECTED_PEER_ID_KEY = "selected_peer_id"

    # Placeholder routes the two selection actions navigate to.
    _VIEW_PROFILE_ROUTE = "/discover/profile"   # view another member's profile
    _CHAT_ROUTE         = "/chat/new"           # start a chat with them

    def __init__(self, page: ft.Page, profile_repo: IProfileRepository) -> None:
        super().__init__(page)
        self.profile_repo = profile_repo
        # Candidates hydrated on mount; kept so the bottom-sheet preview can
        # read full fields without a second backend round-trip.
        self._candidates: list[UserProfile] = []

    # ============================================================
    #  Layout
    # ============================================================

    def get_body(self) -> ft.Control:
        heading = create_screen_heading("אנשים שתרצו להכיר")
        # The profile list — tiles are added on load. STRETCH makes each card
        # fill the full panel width (so a card can never float left); the card's
        # own content is right-aligned internally (see _candidate_tile).
        self._feed_column = ft.Column(
            controls=[],
            spacing=UIConstants.ELEMENT_SPACING,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        return ft.Column(
            controls=[heading, self._feed_column],
            spacing=CONTENT_BODY_SPACING,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def get_actions(self) -> list[ft.Control]:
        return [back_to_menu_button(self.page)]

    def get_status_banner(self) -> ft.Control:
        # Defensive auth / empty / error states. Lives in the sticky bar (not the
        # scroll region), so an empty/error state stays visible however far the
        # feed has scrolled.
        self._status_banner, self._status_text = create_status_banner()
        return self._status_banner

    def on_mount(self) -> None:
        """Mounted into the page tree: start the owned one-shot feed load.
        Cancelled by BaseView.on_unmount when this view is popped/unmounted."""
        self._load_task = self.page.run_task(self._load_candidates)

    # ============================================================
    #  Lifecycle — load the feed
    # ============================================================

    async def _load_candidates(self) -> None:
        # ---- 1. Read identity token. Explicit read (not via a property) so
        # the auth contract is visible at the call site. ----
        current_user_id = self.page.session.store.get(self.SESSION_USER_ID_KEY)

        # ---- 2. Defensive: missing/orphaned token → banner + bounce. ----
        if not current_user_id:
            await show_status(self._status_banner, self._status_text,"אנא התחבר/י תחילה", ok=False)
            await asyncio.sleep(1.5)
            # Route Liveness Check: if the viewer already left during the 1.5s
            # banner, don't yank them back to the login screen.
            if not self._is_live():
                return
            self.page.go("/auth/login")
            return

        # ---- 3. Fetch off the UI thread so the spinner keeps animating. ----
        loading.show_loading(self.page)
        try:
            candidates = await asyncio.to_thread(
                self.profile_repo.discover_profiles,
                current_user_id,
                MatchConfig.DISCOVER_PAGE_SIZE,
            )
        except Exception:                                 # noqa: BLE001 — UI guard
            # Show a calm banner; the raw error goes to the log, never to the
            # senior's screen. (Overlay teardown happens in the finally below.)
            log.exception("Discover: feed load failed for viewer=%s", current_user_id)
            if self._is_live():
                await show_status(self._status_banner, self._status_text,"טעינת האנשים נכשלה. אנא נסה/י שוב מאוחר יותר.", ok=False)
            return
        finally:
            # ALWAYS tear down the overlay — even if the fetch is abandoned by a
            # fast navigation — so the #88000000 scrim can never bleed over the
            # next screen.
            loading.hide_loading(self.page)

        # ---- Route Liveness Check: the await yielded control; if the viewer
        #      navigated away while the feed loaded, abort before mutating a view
        #      that is no longer on screen. ----
        if not self._is_live():
            return

        # ---- 4. Render. Empty feed is a state, not an error. ----
        self._candidates = candidates
        if not candidates:
            await show_status(self._status_banner, self._status_text,
                "עדיין אין פרופילים להצגה. חזרו מאוחר יותר 🙂", ok=False,
            )
            self._feed_column.controls = []
            self.page.update()
            return

        # Render the feed defensively: build each tile in isolation so a single
        # malformed candidate (an unexpected value object slipping past the
        # repository's fail-soft hydration) is SKIPPED with a log line — it can
        # never blank or freeze the whole feed. This is the render-seam analogue
        # of the fetch-seam try/except above (the Peer Layout Boundary Rule
        # applied to a LIST of untrusted records).
        tiles: list[ft.Control] = []
        for p in candidates:
            try:
                tiles.append(self._candidate_tile(p))
            except Exception:  # noqa: BLE001 — one bad row must not kill the feed
                log.exception("Discover: failed to build candidate tile; skipping")
        self._feed_column.controls = tiles
        self.page.update()

    # ============================================================
    #  Candidate tile
    # ============================================================

    def _candidate_tile(self, profile: UserProfile) -> ft.Control:
        """A single tappable member row — name, meta line, presence dot.

        Pure composition: the styling lives in `create_candidate_tile`; this
        method only resolves the profile's data and the tap handler.
        """
        name = profile.display_name.for_gender(profile.gender) or ""
        online = profile.status is AccountStatus.ACTIVE
        return create_candidate_tile(
            name,
            self._meta_line(profile),
            online=online,
            on_click=lambda _e, p=profile: self._on_candidate_tap(p),
        )

    # ============================================================
    #  Selection action sheet (tap a candidate → choose an action)
    # ============================================================

    def _on_candidate_tap(self, profile: UserProfile) -> None:
        """Tapping a candidate opens a senior-friendly selection sheet offering
        the two large action choices: view their profile, or start a chat."""
        sheet = self._build_action_sheet(profile)
        try:
            self.page.open(sheet)                 # Flet ≥0.84
        except AttributeError:
            if sheet not in self.page.overlay:
                self.page.overlay.append(sheet)
            sheet.open = True
            self.page.update()

    def _build_action_sheet(self, profile: UserProfile) -> ft.BottomSheet:
        """RTL bottom sheet: WHO was tapped + exactly two large PRIMARY action
        buttons (view profile / start chat), plus a neutral Close.

        The action labels are long, so the buttons drop to TextSizes.INPUT
        (25px) — still senior-readable — to sit cleanly on the full-width button
        while staying high-contrast brand-red.
        """
        name = profile.display_name.for_gender(profile.gender) or ""
        sheet = ft.BottomSheet(content=ft.Container())   # filled below

        # ---- Who: name + meta line so the senior knows whom they picked ----
        title = ft.Text(
            name,
            size=TextSizes.H2,
            weight=ft.FontWeight.BOLD,
            color=ThemeColors.TEXT_MAIN,
            rtl=True,
            text_align=ft.TextAlign.CENTER,
        )
        subtitle = ft.Text(
            self._meta_line(profile),
            size=TextSizes.INPUT,
            color=ThemeColors.SECONDARY,
            rtl=True,
            text_align=ft.TextAlign.CENTER,
        )
        prompt = ft.Text(
            "מה תרצו לעשות?",
            size=TextSizes.INPUT,
            weight=ft.FontWeight.W_600,
            color=ThemeColors.TEXT_MAIN,
            rtl=True,
            text_align=ft.TextAlign.CENTER,
        )

        # ---- Exactly two distinct, large action buttons ----
        view_button = create_primary_button(
            "צפייה בפרופיל שלו / שלה",
            lambda _e: self._on_action_chosen(sheet, self._VIEW_PROFILE_ROUTE, profile),
            text_size=TextSizes.INPUT,
        )
        chat_button = create_primary_button(
            "התחל שיחה / שלח הודעה",
            lambda _e: self._on_action_chosen(sheet, self._CHAT_ROUTE, profile),
            text_size=TextSizes.INPUT,
        )
        # Neutral dismiss — secondary (blue-grey), never the brand red.
        close_button = create_secondary_button(
            "סגירה", lambda _e: self._close_sheet(sheet),
        )

        sheet.content = ft.Container(
            padding=24,
            bgcolor=ThemeColors.SURFACE,
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
                spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        return sheet

    def _on_action_chosen(
        self, sheet: ft.BottomSheet, route: str, profile: UserProfile,
    ) -> None:
        """Remember the picked peer, dismiss the sheet, then navigate.

        The peer id is stashed in `session.store` under SELECTED_PEER_ID_KEY so
        the (currently placeholder) destination screens can load the right
        person once they're built — mirroring how login stashes the UID before
        routing."""
        self.page.session.store.set(self.SELECTED_PEER_ID_KEY, profile.user_id)
        self._close_sheet(sheet)
        self.page.go(route)

    def _close_sheet(self, sheet: ft.BottomSheet) -> None:
        try:
            self.page.close(sheet)                # Flet ≥0.84
        except AttributeError:
            sheet.open = False
            self.page.update()

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
