"""View Another Member's Profile — read-only, BLACK-SCREEN-PROOF.

Reached from DiscoverView's selection sheet (route `/discover/profile`). That
sheet stashes the chosen member's id in
`page.session.store["selected_peer_id"]` BEFORE navigating here; this view reads
it, loads the profile via `IProfileRepository`, and renders every field as
STATIC text (this is someone else's profile — nothing is editable).

Black-screen elimination (the Peer Layout Boundary Rule)
--------------------------------------------------------
A peer profile is UNTRUSTED, partially-populated data. Three structural guards
ensure it can never blank the screen:

  1. Defensive data parsing — every field is read through a `_safe_*` accessor
     that NEVER raises (null localizations, missing value objects, an empty
     photo array all degrade to a safe default). `_avatar` always paints a solid
     `bgcolor` behind the (fallback-resolved) image, so a failed image load can
     never show black.
  2. Bounded layout — content lives inside `background_screen(translucent_card(…))`
     with a single `expand=True` scroll region; every Column is `STRETCH` and
     every Text is `text_align=RIGHT`/`rtl=True` and wraps within the card width,
     so a long bio cannot overflow Flet's render tree.
  3. Async fail-safe — the fetch runs in `asyncio.to_thread` wrapped in
     try/except; a fetch error, a missing profile, OR a render glitch swaps in a
     styled Hebrew ERROR CARD inside the same shell ("משהו השתבש בטעינת הפרופיל")
     — never a frozen black page. `build()` only assembles static controls, so it
     cannot throw; the router additionally guards every factory (belt + braces).

Architecture
------------
Depends on a SINGLE role-interface, `IProfileRepository` (read-only). Styling
re-uses the shared full-screen background + 50%-white translucent card.
"""
from __future__ import annotations
import asyncio
import logging

import flet as ft

from views._base import BaseView
from views.common.screen import background_screen, translucent_card
from views.common.photos import extra_photo_urls
from components import loading
from components.buttons import create_primary_button, create_secondary_button
from services.I_Profile_Repository import IProfileRepository
from models.user_profile import UserProfile, Gender
from utils.constants import TextSizes, UIConstants, ThemeColors, AssetPaths

log = logging.getLogger(__name__)

# Gender → Hebrew label for the read-only display.
_GENDER_LABELS: dict[Gender, str] = {
    Gender.MALE:   "זכר",
    Gender.FEMALE: "נקבה",
    Gender.OTHER:  "אחר",
}

# Shown whenever a peer's name can't be resolved (null/blank localization).
_FALLBACK_NAME = "משתמש/ת"
# The single Hebrew message for any load/render failure.
_LOAD_ERROR_MSG = "משהו השתבש בטעינת הפרופיל"


class UserProfileView(BaseView):
    """Read-only display of another member's profile."""

    ROUTE = "/discover/profile"

    SELECTED_PEER_ID_KEY = "selected_peer_id"
    _DISCOVER_ROUTE = "/matching/discover"
    _PEER_PHOTOS_ROUTE = "/discover/peer_photos"   # the album + lightbox screen
    _AVATAR_DIAMETER = 104

    def __init__(
        self,
        page: ft.Page,
        profile_repo: IProfileRepository,
        target_peer_id: str = "",
    ) -> None:
        super().__init__(page)
        self.profile_repo = profile_repo
        # §3 Decoupled state — the INJECTED, immutable target id (the router
        # factory passes it directly). This is the PRIMARY channel; the shared
        # session slot is only a tertiary recovery fallback (see
        # `_recover_peer_id_from_session`). Never the logged-in user.
        self._target_peer_id = (target_peer_id or "").strip()
        # The id actually resolved on load; used by the "view album" button.
        self._resolved_peer_id = ""
        # (Task ownership: `self._load_task` is owned by BaseView and cancelled
        # by its on_unmount teardown hook.)

    # ============================================================
    #  Layout (static only — build() must never throw)
    # ============================================================

    def build(self) -> ft.View:
        self._heading = ft.Text(
            "", size=TextSizes.H1, weight=ft.FontWeight.BOLD,
            color=ThemeColors.TEXT_MAIN, rtl=True, text_align=ft.TextAlign.RIGHT,
        )
        # Avatar slot — filled on load; lays out before the profile arrives.
        self._avatar_slot = ft.Container(alignment=ft.Alignment(0, 0))
        # Content slot — holds either the field blocks or an error card.
        self._content = ft.Column(
            controls=[],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        # Bounded, scrollable card: one expand=True scroll region, STRETCH
        # children, RIGHT-aligned text — a long bio wraps and scrolls, it can
        # never overflow the render tree. (The bumped top padding clears the
        # background's top logo.)
        scroll_region = translucent_card(
            ft.Column(
                controls=[self._avatar_slot, self._heading, self._content],
                spacing=16,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            expand=True,
            margin=ft.Margin.only(left=12, top=12, right=12, bottom=8),
            padding=ft.Padding(20, 40, 20, 16),
        )

        # Primary action — "view more photos". Hidden until load confirms the
        # peer actually has album extras (set in _render_profile). Centred via
        # the Column's CENTER alignment, so the fixed-width button is RTL-immune.
        self._album_button = create_primary_button(
            "להצגת תמונות נוספות",
            self._on_view_album,
            text_size=TextSizes.INPUT,   # the label is long → step down from BUTTON
        )
        self._album_button.visible = False

        # Sticky bottom bar — "חזור" is ALWAYS present, so an error card is never
        # a dead end (secondary blue-grey: navigation, per the action hierarchy).
        # The album button sits above it when the peer has extra photos.
        action_bar = ft.Container(
            bgcolor=ft.Colors.TRANSPARENT,
            padding=ft.Padding(24, 12, 24, 20),
            content=ft.Column(
                controls=[
                    self._album_button,
                    create_secondary_button(
                        "חזור", lambda _e: self.page.go(self._DISCOVER_ROUTE),
                    ),
                ],
                tight=True,
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        # The whole layout sits in an explicit expand=True container inside the
        # shared shell — bounded constraints top to bottom.
        view = background_screen(
            self.ROUTE,
            ft.Container(
                expand=True,
                content=ft.Column(
                    controls=[scroll_region, action_bar],
                    expand=True,
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        )

        # Bind the View into the navigation-stack lifecycle (back-ref + Flet
        # did_mount/will_unmount -> our on_mount/on_unmount). The load is started
        # in on_mount (when the page is attached), NOT here — see on_mount.
        return self._bind_lifecycle(view)

    # ============================================================
    #  Lifecycle — load + render, never letting an error blank the page
    # ============================================================

    def on_mount(self) -> None:
        """Mounted into the page tree: start the owned background load. Cancelled
        by BaseView.on_unmount when this view is popped/unmounted."""
        self._load_task = self.page.run_task(self._load_profile)

    def _recover_peer_id_from_session(self) -> str:
        """§3 TERTIARY recovery only. Used when no id was injected (e.g. a
        deep-link straight to this route). Reads the shared session slot and
        returns "" when absent/malformed — never raises."""
        raw = self.page.session.store.get(self.SELECTED_PEER_ID_KEY)
        return raw.strip() if isinstance(raw, str) else ""

    async def _load_profile(self) -> None:
        # Absolute async backstop: the router's two-layer guard only wraps the
        # SYNCHRONOUS build()+mount, so every statement here lives under one total
        # try/except — no async line may escape to the event loop; any failure
        # degrades to the styled error card, never a stuck spinner.
        #
        # NOTE on cancellation: `_on_unmount` cancels this task, raising
        # asyncio.CancelledError at the `await`. CancelledError derives from
        # BaseException (NOT Exception), so it intentionally bypasses every
        # `except Exception` below and unwinds the coroutine cleanly — while the
        # `finally` still runs, keeping the reference-counted overlay balanced.
        try:
            # §3 Decoupled state — INJECTED id is primary; session is tertiary.
            peer_id = self._target_peer_id or self._recover_peer_id_from_session()
            if not peer_id:
                self._show_error_card("לא נבחר משתמש להצגה.")
                return
            self._resolved_peer_id = peer_id

            # show/hide are strictly PAIRED by this try/finally, so the
            # reference-counted overlay is always balanced — on success, on a
            # fetch error, AND on cancellation by a fast back-navigation.
            try:
                loading.show_loading(self.page)
                profile = await asyncio.to_thread(self.profile_repo.get_profile, peer_id)
            except Exception:  # noqa: BLE001 — a fetch error becomes a card, not a crash
                log.exception("UserProfile: load failed for peer=%s", peer_id)
                if self._is_live():
                    self._show_error_card(_LOAD_ERROR_MSG)
                return
            finally:
                loading.hide_loading(self.page)

            # Identity Liveness Guard — immediately after the await. If this
            # instance is no longer the TOP view (covered/popped/replaced) while
            # get_profile ran, it is stale: abort before touching the page.
            if not self._is_live():
                return  # Abort execution silently. This view instance is now stale.

            if profile is None:
                self._show_error_card("הפרופיל לא נמצא.")
                return

            try:
                self._render_profile(profile)
            except Exception:  # noqa: BLE001 — render glitch becomes a card, not a black screen
                log.exception("UserProfile: render failed for peer=%s", peer_id)
                self._show_error_card(_LOAD_ERROR_MSG)
        except Exception:  # noqa: BLE001 — absolute async backstop; nothing escapes the task
            # The loader count is already balanced by the inner finally (or was
            # never incremented), so this backstop must NOT touch the overlay.
            log.exception("UserProfile: unexpected failure in load lifecycle")
            if self._is_live():
                self._show_error_card(_LOAD_ERROR_MSG)

    def _render_profile(self, profile: UserProfile) -> None:
        self._heading.value = self._safe_name(profile)
        self._avatar_slot.content = self._avatar(profile)
        self._content.controls = self._build_field_blocks(profile)
        # Reveal the album button only when the peer has real extra photos
        # (anything beyond the main picture at index 0).
        self._album_button.visible = self._has_album_extras(profile)
        self.page.update()

    def _on_view_album(self, _e: ft.ControlEvent | None = None) -> None:
        """Navigate to the peer's photo album. Re-stash the resolved peer id in
        session.store (the album screen reads it there — this router has no URL
        path params), then go."""
        peer = self._resolved_peer_id or self._target_peer_id
        if peer:
            self.page.session.store.set(self.SELECTED_PEER_ID_KEY, peer)
        self.page.go(self._PEER_PHOTOS_ROUTE)

    @staticmethod
    def _has_album_extras(profile: UserProfile) -> bool:
        """True when the peer has at least one ADDITIONAL photo (index 1+).
        Total — a malformed photo list degrades to 'no extras', never raises."""
        try:
            return len(extra_photo_urls(profile.photo_urls)) > 0
        except Exception:  # noqa: BLE001
            return False

    def _show_error_card(self, message: str) -> None:
        """Replace the content with a styled Hebrew error card inside the shell.
        Defensive everywhere — this is the last line against a black screen."""
        try:
            self._heading.value = ""
            self._avatar_slot.content = None
            self._content.controls = [self._error_card(message)]
            self.page.update()
        except Exception:  # noqa: BLE001 — even the fallback must never raise
            log.exception("UserProfile: failed to show error card")

    # ============================================================
    #  Pure layout builders (no page interaction — unit-testable)
    # ============================================================

    def _build_field_blocks(self, profile: UserProfile) -> list[ft.Control]:
        """Build the read-only label/value blocks from a peer profile.

        Pure (returns Controls; touches no page state) and total: every field is
        read through a `_safe_*` accessor that cannot raise, so a partially
        populated / malformed profile yields fewer blocks — never an exception.
        """
        name = self._safe_name(profile)
        blocks: list[ft.Control] = []

        gender_label = self._safe_gender_label(profile)
        if gender_label:
            blocks.append(self._field("מין", gender_label))

        age = self._safe_age(profile)
        if age:
            blocks.append(self._field("גיל", age))
        dob = self._safe_dob(profile)
        if dob:
            blocks.append(self._field("תאריך לידה", dob))

        location = self._safe_location(profile)
        if location:
            blocks.append(self._field("מיקום", location))

        bio = self._safe_bio(profile)
        if bio and bio != name:        # suppress the username placeholder
            blocks.append(self._field("קצת עליי", bio))

        if not blocks:
            blocks.append(self._field(
                "פרטים נוספים", "המשתמש/ת עדיין לא השלים/ה את הפרופיל.",
            ))
        return blocks

    def _avatar(self, profile: UserProfile) -> ft.Control:
        """The member's main picture, rendered crash-proof on the CLIENT.

        Uses `ft.Image` with an `error_content` initials fallback — NOT
        `ft.DecorationImage` (which has no fallback). If the client can't load
        the src (a stale `data/uploads` path that doesn't exist on this machine,
        an unreadable file, an unsupported src), Flutter renders the initials
        circle instead of failing the render tree to a black screen. A solid
        `bgcolor` sits behind it as a second layer of safety.
        """
        initial = (self._safe_name(profile).strip()[:1] or "?").upper()
        return ft.Container(
            width=self._AVATAR_DIAMETER,
            height=self._AVATAR_DIAMETER,
            border_radius=self._AVATAR_DIAMETER / 2,
            bgcolor=ThemeColors.PRIMARY,
            alignment=ft.Alignment(0, 0),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Image(
                src=self._safe_photo_src(profile),
                width=self._AVATAR_DIAMETER,
                height=self._AVATAR_DIAMETER,
                fit=ft.BoxFit.COVER,
                error_content=ft.Text(
                    initial,
                    size=TextSizes.H1,
                    weight=ft.FontWeight.BOLD,
                    color=ThemeColors.TEXT_ON_PRIMARY,
                ),
            ),
        )

    @staticmethod
    def _error_card(message: str) -> ft.Control:
        """A styled, RTL error card shown inside the translucent shell."""
        return ft.Container(
            bgcolor=ft.Colors.with_opacity(0.12, ThemeColors.DANGER),
            border_radius=UIConstants.CORNER_RADIUS,
            padding=24,
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=ThemeColors.DANGER),
                    ft.Text(
                        message, size=TextSizes.INPUT, weight=ft.FontWeight.W_600,
                        color=ThemeColors.TEXT_MAIN, rtl=True,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "אפשר לחזור ולנסות שוב.", size=TextSizes.BODY,
                        color=ThemeColors.TEXT_MAIN, rtl=True,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    @staticmethod
    def _field(label: str, value: str) -> ft.Control:
        """Read-only label/value block. STRETCH + RIGHT text_align (never END —
        the RTL trap). The value Text wraps within the card width, so even a
        long bio stays inside the layout boundary."""
        return ft.Column(
            controls=[
                ft.Text(
                    label, size=TextSizes.BODY, weight=ft.FontWeight.W_600,
                    color=ThemeColors.SECONDARY, rtl=True,
                    text_align=ft.TextAlign.RIGHT,
                ),
                ft.Text(
                    value, size=TextSizes.INPUT, color=ThemeColors.TEXT_MAIN,
                    rtl=True, text_align=ft.TextAlign.RIGHT, selectable=True,
                    # Wrap (default) within the bounded card; clip the rare
                    # unbroken mega-token so it can't blow the layout width.
                    overflow=ft.TextOverflow.CLIP,
                ),
            ],
            spacing=2,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    # ============================================================
    #  Safe accessors — TOTAL (never raise); the heart of the fix
    # ============================================================

    @staticmethod
    def _safe_str(value: object) -> str:
        return value.strip() if isinstance(value, str) else ""

    def _safe_name(self, profile: UserProfile) -> str:
        try:
            return self._safe_str(profile.display_name.for_gender(profile.gender)) or _FALLBACK_NAME
        except Exception:  # noqa: BLE001
            return _FALLBACK_NAME

    def _safe_bio(self, profile: UserProfile) -> str:
        try:
            return self._safe_str(profile.bio.for_gender(profile.gender))
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _safe_gender_label(profile: UserProfile) -> str | None:
        try:
            return _GENDER_LABELS.get(profile.gender)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _safe_age(profile: UserProfile) -> str | None:
        try:
            dob = profile.date_of_birth
            if dob and dob.year > 1900:          # skip the un-onboarded sentinel
                return str(profile.age)
        except Exception:  # noqa: BLE001
            pass
        return None

    @staticmethod
    def _safe_dob(profile: UserProfile) -> str | None:
        try:
            dob = profile.date_of_birth
            if dob and dob.year > 1900:
                return dob.strftime("%d/%m/%Y")
        except Exception:  # noqa: BLE001
            pass
        return None

    @staticmethod
    def _safe_location(profile: UserProfile) -> str:
        try:
            loc = profile.location
            parts = [p for p in (
                (loc.city or "").strip(), (loc.region or "").strip(),
            ) if p]
            return ", ".join(parts)
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _safe_photo_src(profile: UserProfile) -> str:
        """Resolve the MAIN picture src with an EXPLICIT length guard — never
        assume the photo list coming from the DB is populated. If it's missing,
        empty, or position 0 isn't a usable string, force the default template."""
        try:
            photos = profile.photo_urls
            if photos and len(photos) >= 1 and isinstance(photos[0], str) and photos[0].strip():
                return photos[0]
        except Exception:  # noqa: BLE001 — any access issue → default
            pass
        return AssetPaths.DEFAULT_PROFILE_IMAGE
