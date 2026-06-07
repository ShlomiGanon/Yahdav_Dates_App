"""My Profile — view & edit the logged-in user's own profile.

Architecture
------------
Depends on TWO small role-interfaces, per the project's Interface Segregation
rule: `IProfileRepository` (load/persist the profile + its photo list) and
`IStorageService` (store/delete the photo bytes). It does NOT get
`IAuthService`. The router builds this view like so:

    def _build_my_profile(self) -> ft.View:
        profiles = cast(IProfileRepository,
                        self.page.session.store.get("profiles"))
        storage = cast(IStorageService,
                       self.page.session.store.get("storage"))
        return MyProfileView(self.page, profiles, storage).build()

Photos
------
The top of the page shows the single MAIN profile picture (`photo_urls[0]`, or
the default `UNDEFINED_PROFILE.png` template when none is set). Tapping it picks
a new image and OVERWRITES the main picture (one active picture, ever); the old
file is deleted. Directly underneath sits the "תמונות נוספות" button, which
navigates to `AdditionalPhotosView` (`/profile/photos`) where the portfolio
extras (`photo_urls[1:]`) live — kept separate from the main picture.

Picking a file uses Flet's `ft.FilePicker` service (`pick_files(with_data=True)`
is awaitable in 0.84 — no callback). The raw bytes are written off the UI thread
via `asyncio.to_thread(storage.upload_file, ...)`, and the updated path list is
persisted through `IProfileRepository.save_profile` (UPSERT, never REPLACE).

The view itself pulls the current user_id from `page.session.store` under
the key `"current_user_id"` — populated by `login_view` on successful login.
If that key is missing, the view bounces the user back to `/auth/login`
instead of rendering a broken form.

UX
--
Senior-friendly: oversized labels/inputs from `TextSizes`/`UIConstants`,
RTL throughout, sequential field validation, dedicated red error label
under the affected field, a green success banner that auto-fades, and a
clearly-labelled "חזור לתפריט הראשי" button using the secondary brand colour
so it doesn't compete with the primary "שמור שינויים" action. (Logout now
lives on the Main Menu, not here.)

Layout is split into two regions: a scrollable form area (heading + fields)
that EXPANDS to fill the space and owns the scroll, and a sticky bottom
action bar (status banner + "שמור שינויים" + divider + "חזור לתפריט הראשי")
anchored OUTSIDE the scroll region so the crucial actions and save feedback
are always on-screen and one tap away, however far the form is scrolled.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import date

import flet as ft

from views._base import BaseView
from views.common import renderer as ui
from views.common.navigation import back_to_menu_button
from views.common.photos import resolve_main_photo
from views.common.photo_ops import save_photo_urls_or_rollback
from views.common.load_flow import run_guarded_load, LoadGuard
from components import loading
from components.buttons import create_primary_button
from components.dividers import create_action_divider
from components.inputs import create_hebrew_text_field
from style.design_system import DS
from components.feedback import (
    create_field_error_label, set_field_error, clear_field_errors,
    create_status_banner, show_status,
)
from services.i_profile_repository import IProfileRepository
from services.i_storage_service import IStorageService
from models.user_profile import UserProfile, LocalizedText, Gender, Location
from utils.constants import (
    TextSizes, UIConstants, ThemeColors, StorageConfig, AssetPaths,
)

log = logging.getLogger(__name__)

# Gender dropdown options — key = Gender.value (persisted), text = Hebrew label.
_GENDER_OPTIONS: tuple[tuple[Gender, str], ...] = (
    (Gender.MALE,   "זכר"),
    (Gender.FEMALE, "נקבה"),
    (Gender.OTHER,  "אחר"),
)

# Israeli districts for the Location/Region dropdown. Stored verbatim as the
# free-text `Location.region`.
_REGIONS_HE: tuple[str, ...] = (
    "מחוז הצפון", "מחוז חיפה", "מחוז המרכז", "מחוז תל אביב",
    "מחוז ירושלים", "מחוז הדרום", "יהודה ושומרון",
)

# Age bounds for the birth-year dropdown — legal adult floor, generous ceiling.
_MIN_AGE_YEARS = 18
_MAX_AGE_YEARS = 100


# ----------------------------------------------------------------------------
# View
# ----------------------------------------------------------------------------

class MyProfileView(BaseView):
    ROUTE = "/profile/me"

    # Session-store keys holding the currently logged-in user's identity.
    # Written by login_view on success; read here; cleared on logout.
    # Centralising the strings avoids silent typo drift across files.
    SESSION_USER_ID_KEY    = "current_user_id"
    SESSION_USER_EMAIL_KEY = "current_user_email"

    # Bio is intentionally capped: keeps storage reasonable and the
    # rendered card readable for the 50+ audience.
    _BIO_MAX_CHARS = 1000

    # Route to the additional-photos section, opened by the "תמונות נוספות"
    # button (kept as a literal per the per-view route convention; mirrors
    # AdditionalPhotosView.ROUTE).
    _ADDITIONAL_PHOTOS_ROUTE = "/profile/photos"
    # Main profile-picture display size.
    _MAIN_PHOTO_SIZE = DS.sizing.main_photo

    def __init__(
        self,
        page: ft.Page,
        profile_repo: IProfileRepository,
        storage: IStorageService,
    ) -> None:
        super().__init__(page)
        self.profile_repo = profile_repo
        self.storage = storage
        # The fully-hydrated UserProfile loaded on mount. Mutated in place
        # on save so we preserve every field we didn't touch (gender, DOB,
        # location, safety flags, etc.).
        self._current_profile: UserProfile | None = None
        # Working copy of the photo list (index 0 = MAIN picture, 1..4 = extras).
        # Kept in lock-step with self._current_profile.photo_urls so the two
        # never drift; mutated only after a successful save. This screen edits
        # only index 0; the extras are managed by AdditionalPhotosView.
        self._photo_urls: list[str] = []
        # Flet FilePicker service, attached to the built view (see build()).
        self._file_picker: ft.FilePicker | None = None
        # The main-picture Image control, whose src we refresh on change.
        self._main_image: ft.Image | None = None

    # ============================================================
    #  Layout
    # ============================================================

    def get_header(self) -> ui.UIComponent:
        return ui.heading("הפרופיל שלי")            # CONTENT → right-aligned by the DS

    def _render_body(self) -> ft.Control:
        # Documented exception: this form's fixed-width (400px) fields are CENTRED
        # rather than STRETCHed full-width, so the engine's default body alignment
        # is overridden here (the sanctioned `_render_*` escape hatch). Spacing and
        # everything else still come from the DS via super().
        body = super()._render_body()
        body.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        return body

    def get_content(self) -> list[ui.UIComponent]:
        """Pure content — the stateful controls the handlers mutate (inputs,
        dropdowns, error labels, the photo image) are PRE-BUILT here and embedded
        via `ui.raw(...)` so the view keeps the live refs. The engine owns the body
        layout (spacing; alignment via the `_render_body` override above)."""
        # ---- Photos: main picture + "תמונות נוספות" navigation ----
        # The FilePicker is a Flet *service*; it's attached to THIS view's
        # `services` (not page.services, which still points at the outgoing view
        # while we build). _load_profile_data sets the real main-picture src once
        # the profile is hydrated. The section embeds the mutated _main_image, so
        # it is pre-built and embedded via raw().
        self._file_picker = ft.FilePicker()
        photo_section = self._build_photo_section()

        # ---- Name (Hebrew content → RIGHT-aligned via the shared primitive) ----
        self._name_field = create_hebrew_text_field(
            "שם מלא", hebrew_content=True, on_submit=self._on_save_click,
        )
        self._name_error = create_field_error_label()

        # ---- Bio (multi-line, Hebrew content) ----
        self._bio_field = create_hebrew_text_field(
            "קצת עליי", hebrew_content=True,
            multiline=True, min_lines=4, max_lines=8,
            max_length=self._BIO_MAX_CHARS,
        )
        self._bio_error = create_field_error_label()

        # ---- Gender (large dropdown — no free typing for the 50+ audience) ----
        self._gender_dropdown = self._make_dropdown(
            label="מין",
            options=[ft.dropdown.Option(key=g.value, text=t)
                     for g, t in _GENDER_OPTIONS],
            width=UIConstants.INPUT_WIDTH,
        )
        self._gender_error = create_field_error_label()

        # ---- Birth date — three large dropdowns (day / month / year). ----
        # Deliberately NOT a calendar picker: three simple dropdowns are far
        # easier for seniors than navigating a month grid, and can't produce a
        # malformed date (we still validate the day/month combination on save).
        today = date.today()
        # NOTE on keys vs. text: the option KEY is always the plain integer
        # string (e.g. "9") so it matches `str(date.month/day)` on load and
        # parses straight back via `int(...)` on save. Only the displayed TEXT
        # is zero-padded for a tidy "01..12" look — the stored/parsed value is
        # unaffected.
        self._dob_day = self._make_dropdown(
            label="יום",
            options=[ft.dropdown.Option(key=str(d), text=str(d))
                     for d in range(1, 32)],
            width=UIConstants.DOB_PART_WIDTH,   # wider: room for value + arrow
        )
        self._dob_month = self._make_dropdown(
            label="חודש",
            options=[ft.dropdown.Option(key=str(i), text=f"{i:02d}")
                     for i in range(1, 13)],    # "01".."12" — numbers, not names
            width=UIConstants.DOB_PART_WIDTH,
        )
        self._dob_year = self._make_dropdown(
            label="שנה",
            options=[ft.dropdown.Option(key=str(y), text=str(y))
                     for y in range(today.year - _MIN_AGE_YEARS,
                                    today.year - _MAX_AGE_YEARS - 1, -1)],
            width=UIConstants.DOB_YEAR_WIDTH,
        )
        self._dob_error = create_field_error_label()

        # ---- Location: city (text) + region (dropdown of Israeli districts) ----
        self._city_field = create_hebrew_text_field(
            "עיר", hebrew_content=True, on_submit=self._on_save_click,
        )
        self._city_error = create_field_error_label()
        self._region_dropdown = self._make_dropdown(
            label="אזור",
            options=[ft.dropdown.Option(key=r, text=r) for r in _REGIONS_HE],
            width=UIConstants.INPUT_WIDTH,
        )

        # The scrollable form fields, top → bottom: identity, then demographics,
        # then the free-text bio (longest, so it sits last).
        return [
            ui.raw(photo_section),
            ui.raw(self._name_field),     ui.raw(self._name_error),
            ui.raw(self._gender_dropdown), ui.raw(self._gender_error),
            ui.text("תאריך לידה", size=TextSizes.BODY,
                    weight=ft.FontWeight.W_600, color=ThemeColors.TEXT_MAIN),
            ui.row(
                [ui.raw(self._dob_day), ui.raw(self._dob_month),
                 ui.raw(self._dob_year)],
                spacing=DS.spacing.sm,
                width=DS.sizing.input_w,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ui.raw(self._dob_error),
            ui.raw(self._city_field),     ui.raw(self._city_error),
            ui.raw(self._region_dropdown),
            ui.raw(self._bio_field),      ui.raw(self._bio_error),
        ]

    def get_actions(self) -> list[ui.UIComponent]:
        # Primary "save" (red) above a divider above the secondary (blue-grey)
        # "return to menu", so a senior never confuses the two.
        return [
            ui.primary_button("שמור שינויים", self._on_save_click),
            ui.raw(create_action_divider(
                width=DS.sizing.input_w, height=DS.sizing.divider_h_tall,
            )),
            ui.raw(back_to_menu_button(self.page)),
        ]

    def get_status_banner(self) -> ui.UIComponent:
        # Inline success/error feedback (reliable across Flet versions — no
        # dependency on page.snack_bar). Sits above the buttons in the sticky bar.
        self._status_banner, self._status_text = create_status_banner(
            width=DS.sizing.input_w,
        )
        return ui.raw(self._status_banner)

    def get_services(self) -> list[ft.Control]:
        # The FilePicker mounts + registers with THIS view (discarded on nav).
        return [self._file_picker]

    def on_mount(self) -> None:
        """Mounted into the page tree: start the owned one-shot profile load.
        Cancelled by BaseView.on_unmount when this view is popped/unmounted."""
        self._load_task = self.page.run_task(self._load_profile_data)

    # ============================================================
    #  Lifecycle — fetch profile on mount and populate the form
    # ============================================================

    async def _load_profile_data(self) -> None:
        # Identity read kept explicit at the call site so the auth contract is
        # visible; the guard/spinner/liveness scaffolding lives in the shared
        # run_guarded_load (views/common/load_flow.py). The fetch is a pure,
        # WRITE-FREE read — the lazy photo-heal is dispatched separately in
        # _populate so the critical load never triggers a WAL UPDATE.
        current_user = self.page.session.store.get(self.SESSION_USER_ID_KEY)

        async def _populate(profile: UserProfile | None) -> None:
            # Profile may legitimately not exist (e.g. orphaned UID).
            if profile is None:
                await show_status(self._status_banner, self._status_text,
                    "לא נמצא פרופיל. אנא התחבר/י מחדש.", ok=False,
                )
                await asyncio.sleep(1.5)
                self.page.go("/auth/login")
                return

            # Lazy migration — fully DECOUPLED, fire-and-forget AFTER the read.
            self._schedule_photo_heal(current_user)

            self._current_profile = profile
            self._populate_form(profile)
            self.page.update()

        await run_guarded_load(
            self.page,
            guards=[LoadGuard(
                ok=bool(current_user),
                message="אנא התחבר/י תחילה כדי לראות את הפרופיל שלך.",
                bounce=lambda: self._is_live() and self.page.go("/auth/login"),
            )],
            fetch=lambda: self.profile_repo.get_profile(current_user),
            on_success=_populate,
            is_stale=lambda: not self._is_live(),
            status_banner=self._status_banner,
            status_text=self._status_text,
            logger=log,
            fetch_error_message="טעינת הפרופיל נכשלה. אנא נסה/י שוב מאוחר יותר.",
            fetch_error_log=f"MyProfile: profile load failed for user={current_user}",
        )

    def _populate_form(self, profile: UserProfile) -> None:
        """Fill every form field from the loaded profile (pure UI population)."""
        self._name_field.value = profile.display_name.for_gender(profile.gender)
        self._bio_field.value  = profile.bio.for_gender(profile.gender)

        # Gender — dropdown key is the persisted Gender.value.
        self._gender_dropdown.value = profile.gender.value

        # Birth date — populate the three dropdowns, but skip the 1900-01-01
        # sentinel a not-yet-onboarded profile carries, so the senior is
        # prompted to actually pick their date rather than seeing a fake one.
        dob = profile.date_of_birth
        if dob.year > 1900:
            self._dob_day.value   = str(dob.day)
            self._dob_month.value = str(dob.month)
            self._dob_year.value  = str(dob.year)

        # Location — city verbatim; region only if it matches a known option
        # (the underlying field is free-text and may hold a legacy value).
        loc = profile.location
        self._city_field.value = loc.city or ""
        self._region_dropdown.value = loc.region if loc.region in _REGIONS_HE else None

        # Photos — seed the working copy from the loaded profile and paint the
        # main picture. Capped defensively at MAX_PROFILE_PHOTOS in case a legacy
        # row carries more.
        self._photo_urls = list(profile.photo_urls)[:StorageConfig.MAX_PROFILE_PHOTOS]
        self._refresh_main_photo()

    def _schedule_photo_heal(self, user_id: str) -> None:
        """Fire-and-forget the lazy photo migration, off the read path.

        Kept OUT of `_load_profile_data`'s fetch sequence so the profile read
        stays write-free: the heal is an independent background task, never
        awaited by the load and unable to stall the render. `ensure_default_photo`
        is itself conditional + idempotent + best-effort, so a redundant or
        failed run is harmless."""
        async def _heal() -> None:
            try:
                await asyncio.to_thread(
                    self.profile_repo.ensure_default_photo, user_id,
                )
            except Exception:  # noqa: BLE001 — migration must never disturb the view
                log.warning("MyProfile: background photo heal failed user=%s",
                            user_id, exc_info=True)
        try:
            self.page.run_task(_heal)
        except AttributeError:
            asyncio.create_task(_heal())

    # ============================================================
    #  Save handler
    # ============================================================

    async def _on_save_click(self, e: ft.ControlEvent) -> None:
        self._clear_errors()

        name = (self._name_field.value or "").strip()
        bio  = (self._bio_field.value  or "").strip()
        city = (self._city_field.value or "").strip()

        # ---- Sequential field validation (first failure wins, one banner) ----
        if not name:
            set_field_error(self._name_error, "שדה השם הוא חובה")
            return

        gender_key = self._gender_dropdown.value
        if not gender_key:
            set_field_error(self._gender_error, "אנא בחר/י מין")
            return

        birth = self._validated_birth_date()
        if birth is None:
            return  # the helper already pinned the birth-date error label

        if not city:
            set_field_error(self._city_error, "שדה העיר הוא חובה")
            return

        # ---- Defensive: profile must have loaded before we can mutate it ----
        if self._current_profile is None:
            await show_status(self._status_banner, self._status_text,
                "לא ניתן לשמור — הפרופיל לא נטען. נסה/י לרענן את המסך.",
                ok=False,
            )
            return

        # ---- Safe mutation — PUBLIC setters only, edited fields only ----
        # We mutate ONLY the fields the form owns and leave everything else on
        # the loaded entity exactly as it was (user_id, email, registered_at,
        # status, safety_flags, photos, lat/lon…). Combined with the repository's
        # UPSERT (never REPLACE), saving a profile can never drop credentials,
        # system IDs, or untouched columns. display_name / bio are first-person
        # ("about me"), so the same string is mirrored across all three variants.
        self._current_profile.display_name = LocalizedText(
            he_male=name, he_female=name, he_neutral=name,
        )
        self._current_profile.bio = LocalizedText(
            he_male=bio, he_female=bio, he_neutral=bio,
        )
        self._current_profile.gender = Gender(gender_key)
        self._current_profile.date_of_birth = birth
        # Preserve the geo fields the form doesn't edit (lat / lon / radius);
        # only city + region come from the UI.
        existing_loc = self._current_profile.location
        self._current_profile.location = Location(
            city=city,
            region=self._region_dropdown.value or None,
            lat=existing_loc.lat,
            lon=existing_loc.lon,
            visibility_radius_km=existing_loc.visibility_radius_km,
        )

        # ---- Persist (blocking → off the UI thread) ----
        loading.show_loading(self.page)
        try:
            await asyncio.to_thread(
                self.profile_repo.save_profile, self._current_profile,
            )
        except Exception:
            # save_profile can raise ValueError (duplicate email/phone) OR a
            # re-raised sqlite3.Error (locked/corrupt DB). Catch broadly so a
            # storage hiccup can NEVER leave the spinner stuck or crash the
            # handler. Log the technical cause; show the senior a calm banner.
            loading.hide_loading(self.page)
            log.exception(
                "MyProfile: save failed for user=%s",
                self._current_profile.user_id,
            )
            await show_status(self._status_banner, self._status_text,
                "שמירת הפרופיל נכשלה. אנא נסה/י שוב.", ok=False,
            )
            return
        loading.hide_loading(self.page)

        # Success banner auto-fades so the user can keep editing.
        await show_status(self._status_banner, self._status_text,
            "הפרופיל עודכן בהצלחה!", ok=True, auto_hide_sec=3.0,
        )

    def _validated_birth_date(self) -> date | None:
        """Read the day/month/year dropdowns into a real `date`.

        Returns the `date` on success; otherwise sets the birth-date error
        label and returns None. Rejects an incomplete selection, an impossible
        calendar date (e.g. 31 בפברואר), and ages outside the allowed bounds.
        """
        d = self._dob_day.value
        m = self._dob_month.value
        y = self._dob_year.value
        if not (d and m and y):
            set_field_error(
                self._dob_error, "אנא בחר/י תאריך לידה מלא (יום, חודש ושנה)",
            )
            return None
        try:
            birth = date(int(y), int(m), int(d))
        except ValueError:
            set_field_error(self._dob_error, "התאריך שנבחר אינו קיים בלוח השנה")
            return None
        today = date.today()
        age = today.year - birth.year - (
            (today.month, today.day) < (birth.month, birth.day)
        )
        if age < _MIN_AGE_YEARS:
            set_field_error(
                self._dob_error,
                f"הגיל המינימלי לשימוש באפליקציה הוא {_MIN_AGE_YEARS}",
            )
            return None
        if age > _MAX_AGE_YEARS:
            set_field_error(self._dob_error, "אנא בדוק/י את שנת הלידה שנבחרה")
            return None
        return birth

    # ============================================================
    #  Main profile picture + "additional photos" navigation
    # ============================================================

    def _build_photo_section(self) -> ft.Control:
        """The MAIN profile picture at the top (tappable to change/overwrite),
        with the "תמונות נוספות" button directly underneath. The portfolio
        extras themselves live on AdditionalPhotosView."""
        # Start on the default template; _refresh_main_photo swaps in the real
        # main picture once the profile is hydrated on mount.
        self._main_image = ft.Image(
            src=resolve_main_photo(self._photo_urls),
            width=self._MAIN_PHOTO_SIZE,
            height=self._MAIN_PHOTO_SIZE,
            fit=ft.BoxFit.COVER,
            error_content=ft.Icon(
                ft.Icons.ACCOUNT_CIRCLE,
                size=self._MAIN_PHOTO_SIZE,
                color=ThemeColors.SECONDARY,
            ),
        )
        # The whole picture is the tap target to change it (ink ripple + camera
        # badge). One active picture: picking a new one OVERWRITES it.
        main_picture = ft.Container(
            width=self._MAIN_PHOTO_SIZE,
            height=self._MAIN_PHOTO_SIZE,
            border_radius=self._MAIN_PHOTO_SIZE / 2,   # circular avatar
            bgcolor=ft.Colors.with_opacity(DS.opacity.tile_bg, ThemeColors.SECONDARY),
            alignment=ft.Alignment(0, 0),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ink=True,
            on_click=self._on_change_main_photo,
            tooltip="הקש/י כדי לעדכן את תמונת הפרופיל",
            content=ft.Stack(
                controls=[
                    self._main_image,
                    # Small camera badge, bottom-start, hinting "tap to change".
                    ft.Container(
                        alignment=ft.Alignment(0, 1),
                        content=ft.Container(
                            bgcolor=ft.Colors.with_opacity(DS.opacity.badge, ft.Colors.BLACK),
                            padding=DS.pad.badge,
                            content=ft.Icon(
                                ft.Icons.PHOTO_CAMERA,
                                size=DS.sizing.icon_sm,
                                color=ft.Colors.WHITE,
                            ),
                        ),
                    ),
                ],
                width=self._MAIN_PHOTO_SIZE,
                height=self._MAIN_PHOTO_SIZE,
            ),
        )
        change_hint = ft.Text(
            "הקש/י על התמונה כדי לעדכן את תמונת הפרופיל",
            size=TextSizes.SMALL,
            color=ThemeColors.TEXT_MAIN,
            rtl=True,
            text_align=ft.TextAlign.CENTER,
        )
        # The existing photo button, relocated under the picture and relabelled.
        additional_button = create_primary_button(
            "תמונות נוספות",
            lambda _e: self.page.go(self._ADDITIONAL_PHOTOS_ROUTE),
            text_size=TextSizes.INPUT,
        )
        return ft.Column(
            controls=[main_picture, change_hint, additional_button],
            spacing=DS.spacing.md,
            width=DS.sizing.input_w,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _refresh_main_photo(self) -> None:
        """Repaint the main picture from the current working copy (real main at
        index 0, or the default template)."""
        if self._main_image is None:
            return
        self._main_image.src = resolve_main_photo(self._photo_urls)
        try:
            self._main_image.update()
        except Exception:
            pass  # not yet mounted — the caller's page.update() will flush it

    async def _on_change_main_photo(self, e: ft.ControlEvent) -> None:
        """Pick an image and OVERWRITE the single main picture (index 0).

        Durability order: write the new file FIRST, then UPSERT the profile;
        only after the save succeeds do we delete the OLD main file (never the
        bundled default template). A save failure rolls back and deletes the
        just-written orphan."""
        if self._current_profile is None:
            await show_status(self._status_banner, self._status_text,
                "לא ניתן לעדכן תמונה — הפרופיל לא נטען. נסה/י לרענן את המסך.",
                ok=False,
            )
            return
        if self._file_picker is None:   # defensive: build() always sets it
            await show_status(self._status_banner, self._status_text,"בורר הקבצים אינו זמין כעת.", ok=False)
            return

        # In Flet 0.84 `pick_files` is awaitable and returns the selection
        # DIRECTLY (no on_result callback). with_data=True reads the raw bytes.
        try:
            files = await self._file_picker.pick_files(
                dialog_title="בחר/י תמונת פרופיל",
                file_type=ft.FilePickerFileType.IMAGE,
                allow_multiple=False,
                with_data=True,
            )
        except Exception:
            log.exception("MyProfile: file picker failed")
            await show_status(self._status_banner, self._status_text,"פתיחת בורר הקבצים נכשלה. אנא נסה/י שוב.", ok=False)
            return
        if not files:            # user cancelled the dialog
            return
        data = files[0].bytes
        if not data:
            await show_status(self._status_banner, self._status_text,"טעינת התמונה נכשלה. נסה/י קובץ אחר.", ok=False)
            return

        old_main = self._photo_urls[0] if self._photo_urls else None

        loading.show_loading(self.page)
        stored_path: str | None = None
        try:
            stored_path = await asyncio.to_thread(
                self.storage.upload_file, data, files[0].name,
            )
            # Overwrite index 0 (or create it). Extras at index 1+ are untouched.
            new_list = list(self._photo_urls)
            if new_list:
                new_list[0] = stored_path
            else:
                new_list = [stored_path]
            # Shared durability kernel: UPSERT the new list, rolling the entity
            # back and deleting the just-uploaded orphan if the save fails.
            await save_photo_urls_or_rollback(
                self.profile_repo, self._current_profile, new_list,
                previous_photo_urls=self._photo_urls,
                storage=self.storage, orphan_path=stored_path,
            )
        except Exception:
            loading.hide_loading(self.page)
            log.exception("MyProfile: change main photo failed for user=%s",
                          self._current_profile.user_id)
            await show_status(self._status_banner, self._status_text,"עדכון תמונת הפרופיל נכשל. אנא נסה/י שוב.", ok=False)
            return
        loading.hide_loading(self.page)

        # Commit, then delete the OLD main file — but never the bundled default
        # template (delete_file refuses it anyway, as it's outside the root).
        if self._photo_urls:
            self._photo_urls[0] = stored_path
        else:
            self._photo_urls = [stored_path]
        if old_main and old_main != AssetPaths.DEFAULT_PROFILE_IMAGE:
            await asyncio.to_thread(self.storage.delete_file, old_main)

        self._refresh_main_photo()
        await show_status(self._status_banner, self._status_text,"תמונת הפרופיל עודכנה בהצלחה!", ok=True, auto_hide_sec=3.0)

    # ============================================================
    #  Error / status helpers
    # ============================================================

    @staticmethod
    def _make_dropdown(
        *,
        label: str,
        options: list[ft.dropdown.Option],
        width: float,
    ) -> ft.Dropdown:
        """Senior-friendly dropdown: oversized label + option text, fixed width.

        A dropdown (closed list) is deliberately preferred over a free-text
        field for gender / region / date parts — there is nothing to mistype,
        and the large tap target suits the 50+ audience.
        """
        return ft.Dropdown(
            label=label,
            label_style=ft.TextStyle(size=TextSizes.INPUT),
            options=options,
            width=width,
            text_size=TextSizes.INPUT,
        )

    def _clear_errors(self) -> None:
        clear_field_errors(
            self._name_error,
            self._gender_error,
            self._dob_error,
            self._city_error,
            self._bio_error,
        )
        self.page.update()
