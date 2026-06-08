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
the key `SESSION_USER_ID_KEY` — populated by `login_view` on successful login.
If that key is missing, the view bounces the user back to `/auth/login`
instead of rendering a broken form.

UX
--
Senior-friendly: oversized labels/inputs from `DS.type`/`DS.sizing`,
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
from views.common.engine import renderer as ui
from views.common.helpers.navigation import back_to_menu_button
from views.common.helpers.load_flow import run_guarded_load, LoadGuard
from views.profile import my_profile_form as profile_form
from views.profile import my_profile_photos as profile_photos
from components import loading
from components.dividers import create_action_divider
from style.design_system import DS
from components.feedback import set_field_error, create_status_banner, show_status
from services.interfaces.i_profile_repository import IProfileRepository
from services.interfaces.i_storage_service import IStorageService
from models.user_profile import UserProfile, Gender, GENDER_LABELS_HE
from utils.constants import StorageConfig
from utils.session_keys import CURRENT_USER_ID, CURRENT_USER_EMAIL
from utils import routes

log = logging.getLogger(__name__)

# Gender dropdown options — key = Gender.value (persisted), text = Hebrew label.
# Derived from the canonical `GENDER_LABELS_HE` map (preserves its
# MALE → FEMALE → OTHER insertion order).
_GENDER_OPTIONS: tuple[tuple[Gender, str], ...] = tuple(GENDER_LABELS_HE.items())

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
    ROUTE = routes.MY_PROFILE

    EXPAND_BODY = True   # long profile form → fill the viewport, scroll internally

    # Session-store keys holding the currently logged-in user's identity.
    # Written by login_view on success; read here; cleared on logout.
    # Aliases of the canonical `utils.session_keys` constants.
    SESSION_USER_ID_KEY    = CURRENT_USER_ID
    SESSION_USER_EMAIL_KEY = CURRENT_USER_EMAIL

    # Bio is intentionally capped: keeps storage reasonable and the
    # rendered card readable for the 50+ audience.
    _BIO_MAX_CHARS = 1000

    # Route to the additional-photos section, opened by the "תמונות נוספות"
    # button (kept as a literal per the per-view route convention; mirrors
    # AdditionalPhotosView.ROUTE).
    _ADDITIONAL_PHOTOS_ROUTE = routes.ADDITIONAL_PHOTOS
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
        return ui.heading("הפרופיל שלי")

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
        self._main_image, photo_section = profile_photos.build_photo_section(
            photo_urls=self._photo_urls,
            size=self._MAIN_PHOTO_SIZE,
            on_change_main_photo=self._on_change_main_photo,
            on_open_additional=lambda _e: self.page.go(self._ADDITIONAL_PHOTOS_ROUTE),
        )

        # ---- Form fields — built via the stateless `my_profile_form` factories;
        # the resulting refs are OUR instance attributes (single source of truth
        # the load/save handlers mutate). ----
        self._name_field, self._name_error = profile_form.build_name_field(
            self._on_save_click,
        )
        self._bio_field, self._bio_error = profile_form.build_bio_field(
            self._BIO_MAX_CHARS,
        )
        self._gender_dropdown, self._gender_error = profile_form.build_gender_dropdown(
            _GENDER_OPTIONS,
        )
        (self._dob_day, self._dob_month, self._dob_year,
         self._dob_error) = profile_form.build_dob_dropdowns(
            _MIN_AGE_YEARS, _MAX_AGE_YEARS,
        )
        (self._city_field, self._city_error,
         self._region_dropdown) = profile_form.build_location_fields(
            self._on_save_click, _REGIONS_HE,
        )

        # The scrollable form fields, top → bottom: identity, then demographics,
        # then the free-text bio (longest, so it sits last).
        return [
            ui.raw(photo_section),
            ui.raw(self._name_field),     ui.raw(self._name_error),
            ui.raw(self._gender_dropdown), ui.raw(self._gender_error),
            ui.text("תאריך לידה", size=DS.type.body,
                    weight=ft.FontWeight.W_600, color=DS.palette.text_main),
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
                self.page.go(routes.LOGIN)
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
                bounce=lambda: self._is_live() and self.page.go(routes.LOGIN),
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
        """Fill every form field from the loaded profile (pure UI population),
        then seed the photo working copy and repaint the main picture."""
        profile_form.populate_form(
            profile,
            name_field=self._name_field, bio_field=self._bio_field,
            gender_dropdown=self._gender_dropdown,
            dob_day=self._dob_day, dob_month=self._dob_month, dob_year=self._dob_year,
            city_field=self._city_field, region_dropdown=self._region_dropdown,
            known_regions=_REGIONS_HE,
        )

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

        # ---- Apply the validated values onto the loaded entity (PUBLIC
        # setters, edited fields only — see my_profile_form.apply_edits for
        # why this can never drop credentials/system fields) ----
        profile_form.apply_edits(
            self._current_profile,
            name=name, bio=bio, gender_key=gender_key, birth=birth,
            city=city, region=self._region_dropdown.value or None,
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
        """Read the day/month/year dropdowns into a real `date`, or pin the
        birth-date error label and return None. See `my_profile_form
        .validated_birth_date` for the full validation rules."""
        return profile_form.validated_birth_date(
            self._dob_day, self._dob_month, self._dob_year, self._dob_error,
            min_age_years=_MIN_AGE_YEARS, max_age_years=_MAX_AGE_YEARS,
        )

    # ============================================================
    #  Main profile picture + "additional photos" navigation
    # ============================================================
    # The section layout, repaint, and change/upload flow are stateless
    # helpers in `my_profile_photos` — WE remain the sole owner of
    # `_main_image`/`_current_profile`/`_photo_urls` (passed in, mutated in
    # place) so the load/save/photo handlers keep one shared source of truth.

    def _refresh_main_photo(self) -> None:
        profile_photos.refresh_main_photo(self._main_image, self._photo_urls)

    async def _on_change_main_photo(self, e: ft.ControlEvent) -> None:
        await profile_photos.on_change_main_photo(
            page=self.page,
            file_picker=self._file_picker,
            profile_repo=self.profile_repo,
            storage=self.storage,
            current_profile=self._current_profile,
            photo_urls=self._photo_urls,
            status_banner=self._status_banner,
            status_text=self._status_text,
            refresh=self._refresh_main_photo,
        )

    # ============================================================
    #  Error / status helpers
    # ============================================================

    def _clear_errors(self) -> None:
        profile_form.clear_errors(
            self.page,
            self._name_error,
            self._gender_error,
            self._dob_error,
            self._city_error,
            self._bio_error,
        )
