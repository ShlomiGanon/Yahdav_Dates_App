"""Additional Photos — manage a member's portfolio extras (NOT the main picture).

Reached from `MyProfileView` via the "תמונות נוספות" button (route
`/profile/photos`). The MAIN profile picture (index 0 of `photo_urls`) is owned
and edited on the profile page; THIS screen manages only the ADDITIONAL photos
(`photo_urls[1:]`, up to `StorageConfig.MAX_EXTRA_PHOTOS`), kept separate from
the main picture per the product requirement.

Architecture
------------
Like `MyProfileView` it depends on TWO role-interfaces — `IProfileRepository`
(persist the photo list) and `IStorageService` (store/delete the bytes) — and
reads `current_user_id` from `page.session.store`, bouncing to `/auth/login` if
it's missing. Index 0 is always reserved for the main picture: adding the first
extra to a profile with no real main seeds the default template at index 0 so an
extra never silently becomes the main picture.
"""
from __future__ import annotations
import asyncio
import functools
import logging

import flet as ft

from views._base import BaseView
from views.common import renderer as ui
from views.common.navigation import back_to_menu_button, back_button
from style.design_system import DS
from views.common.photos import DEFAULT_PROFILE_IMAGE, extra_photo_urls, photo_thumb
from views.common.photo_ops import save_photo_urls_or_rollback
from views.common.load_flow import run_guarded_load, LoadGuard
from components import loading
from components.buttons import create_primary_button, create_secondary_button
from components.feedback import create_status_banner, show_status
from services.i_profile_repository import IProfileRepository
from services.i_storage_service import IStorageService
from models.user_profile import UserProfile
from utils.constants import TextSizes, UIConstants, ThemeColors, StorageConfig

log = logging.getLogger(__name__)


class AdditionalPhotosView(BaseView):
    ROUTE = "/profile/photos"

    SESSION_USER_ID_KEY = "current_user_id"
    _PROFILE_ROUTE = "/profile/me"
    _THUMB_SIZE = DS.sizing.thumb

    def __init__(
        self,
        page: ft.Page,
        profile_repo: IProfileRepository,
        storage: IStorageService,
    ) -> None:
        super().__init__(page)
        self.profile_repo = profile_repo
        self.storage = storage
        self._current_profile: UserProfile | None = None
        # Full working copy (index 0 = main, 1.. = extras); kept in lock-step
        # with the profile and mutated only after a successful save.
        self._photo_urls: list[str] = []
        self._file_picker: ft.FilePicker | None = None
        self._photos_area: ft.Column | None = None
        self._status_text: ft.Text | None = None
        self._status_banner: ft.Container | None = None

    # ============================================================
    #  Layout
    # ============================================================

    def get_header(self) -> ui.UIComponent:
        return ui.heading("תמונות נוספות")

    def get_content(self) -> list[ui.UIComponent]:
        # The photos area is populated at runtime (_refresh_photos), so it is
        # PRE-BUILT and embedded via raw(); the hint is declarative. STRETCH so
        # tiles span the card width and right-align via text_align.
        self._file_picker = ft.FilePicker()
        self._photos_area = ft.Column(
            spacing=DS.spacing.md,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        return [
            ui.text(
                f"ניתן להוסיף עד {StorageConfig.MAX_EXTRA_PHOTOS} תמונות, "
                f"בנוסף לתמונת הפרופיל הראשית.",
                size=TextSizes.SMALL,
                color=ThemeColors.TEXT_MAIN,
            ),
            ui.raw(self._photos_area),
        ]

    def get_actions(self) -> list[ui.UIComponent]:
        # Stack-aware "back to profile" (profile is the only entry point) + the
        # menu button (UNWIND to /menu).
        return [
            ui.raw(back_button(
                self.page, label="חזרה לפרופיל", fallback=self._PROFILE_ROUTE,
            )),
            ui.raw(back_to_menu_button(self.page)),
        ]

    def get_status_banner(self) -> ui.UIComponent:
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
    #  Lifecycle
    # ============================================================

    async def _load_profile_data(self) -> None:
        # Identity read kept explicit; the guard/spinner/liveness scaffolding is
        # the shared run_guarded_load (views/common/load_flow.py).
        current_user = self.page.session.store.get(self.SESSION_USER_ID_KEY)

        async def _populate(profile: UserProfile | None) -> None:
            if profile is None:
                await show_status(self._status_banner, self._status_text,"לא נמצא פרופיל. אנא התחבר/י מחדש.", ok=False)
                await asyncio.sleep(1.5)
                self.page.go("/auth/login")
                return
            self._current_profile = profile
            self._photo_urls = list(profile.photo_urls)[:StorageConfig.MAX_PROFILE_PHOTOS]
            self._refresh_photos()
            self.page.update()

        await run_guarded_load(
            self.page,
            guards=[LoadGuard(
                ok=bool(current_user),
                message="אנא התחבר/י תחילה.",
                bounce=lambda: self._is_live() and self.page.go("/auth/login"),
            )],
            fetch=lambda: self.profile_repo.get_profile(current_user),
            on_success=_populate,
            is_stale=lambda: not self._is_live(),
            status_banner=self._status_banner,
            status_text=self._status_text,
            logger=log,
            fetch_error_message="טעינת התמונות נכשלה. אנא נסה/י שוב.",
            fetch_error_log=f"AdditionalPhotos: load failed user={current_user}",
        )

    # ============================================================
    #  Rendering
    # ============================================================

    def _extras(self) -> list[str]:
        """The additional photos (everything after the main picture)."""
        return extra_photo_urls(self._photo_urls)

    def _refresh_photos(self) -> None:
        if self._photos_area is None:
            return
        extras = self._extras()
        tiles: list[ft.Control] = []
        if not extras:
            tiles.append(ft.Text(
                "עדיין לא הוספת תמונות נוספות.",
                size=TextSizes.BODY, color=ThemeColors.TEXT_MAIN,
                rtl=True, text_align=ft.TextAlign.RIGHT,
            ))
        for i, path in enumerate(extras):
            tiles.append(self._make_tile(path, i))
        if len(extras) < StorageConfig.MAX_EXTRA_PHOTOS:
            tiles.append(create_primary_button(
                "הוסף תמונה נוספת", self._on_add_photo, text_size=TextSizes.INPUT,
            ))
        self._photos_area.controls = tiles
        try:
            self._photos_area.update()
        except Exception:
            pass  # not yet mounted — the caller's page.update() will flush it

    def _make_tile(self, path: str, extra_index: int) -> ft.Control:
        """One extra-photo row: thumbnail RIGHT (RTL first child), caption +
        70px remove button filling the space to its left."""
        caption = ft.Text(
            f"תמונה {extra_index + 1}",
            size=TextSizes.INPUT, weight=ft.FontWeight.W_500,
            color=ThemeColors.TEXT_MAIN, rtl=True, text_align=ft.TextAlign.RIGHT,
        )
        remove_btn = create_secondary_button(
            "הסר תמונה",
            functools.partial(self._on_remove_photo, extra_index),
            width=None,
            height=DS.sizing.button_h,   # 70px tap target
            text_size=TextSizes.INPUT,
        )
        info = ft.Column(
            controls=[caption, remove_btn],
            spacing=DS.spacing.sm, expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        return ft.Row(
            controls=[photo_thumb(path, size=self._THUMB_SIZE), info],
            spacing=DS.spacing.md,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    # ============================================================
    #  Handlers
    # ============================================================

    async def _on_add_photo(self, e: ft.ControlEvent) -> None:
        if self._current_profile is None:
            await show_status(self._status_banner, self._status_text,"לא ניתן להוסיף — הפרופיל לא נטען.", ok=False)
            return
        if len(self._extras()) >= StorageConfig.MAX_EXTRA_PHOTOS:
            await show_status(self._status_banner, self._status_text,
                f"ניתן להוסיף עד {StorageConfig.MAX_EXTRA_PHOTOS} תמונות נוספות.",
                ok=False,
            )
            return
        if self._file_picker is None:
            await show_status(self._status_banner, self._status_text,"בורר הקבצים אינו זמין כעת.", ok=False)
            return

        try:
            files = await self._file_picker.pick_files(
                dialog_title="בחר/י תמונה",
                file_type=ft.FilePickerFileType.IMAGE,
                allow_multiple=False,
                with_data=True,
            )
        except Exception:
            log.exception("AdditionalPhotos: file picker failed")
            await show_status(self._status_banner, self._status_text,"פתיחת בורר הקבצים נכשלה.", ok=False)
            return
        if not files:
            return
        data = files[0].bytes
        if not data:
            await show_status(self._status_banner, self._status_text,"טעינת התמונה נכשלה. נסה/י קובץ אחר.", ok=False)
            return

        loading.show_loading(self.page)
        stored_path: str | None = None
        try:
            stored_path = await asyncio.to_thread(
                self.storage.upload_file, data, files[0].name,
            )
            # Reserve index 0 for the main picture: if there's no real main yet,
            # seed the default template so this extra lands at index >= 1.
            base = list(self._photo_urls) or [DEFAULT_PROFILE_IMAGE]
            new_list = base + [stored_path]
            # Shared durability kernel: UPSERT the new list, rolling the entity
            # back and deleting the just-uploaded orphan if the save fails.
            await save_photo_urls_or_rollback(
                self.profile_repo, self._current_profile, new_list,
                previous_photo_urls=self._photo_urls,
                storage=self.storage, orphan_path=stored_path,
            )
        except Exception:
            loading.hide_loading(self.page)
            log.exception("AdditionalPhotos: add failed user=%s",
                          self._current_profile.user_id)
            await show_status(self._status_banner, self._status_text,"שמירת התמונה נכשלה. אנא נסה/י שוב.", ok=False)
            return
        loading.hide_loading(self.page)

        self._photo_urls = new_list
        self._refresh_photos()
        await show_status(self._status_banner, self._status_text,"התמונה נוספה בהצלחה!", ok=True, auto_hide_sec=3.0)

    async def _on_remove_photo(self, extra_index: int, e: ft.ControlEvent) -> None:
        # Map the extra's index back to the absolute photo_urls index (+1 for
        # the main picture at index 0).
        abs_index = extra_index + 1
        if self._current_profile is None or not (1 <= abs_index < len(self._photo_urls)):
            return
        removed_path = self._photo_urls[abs_index]
        new_list = [p for i, p in enumerate(self._photo_urls) if i != abs_index]

        loading.show_loading(self.page)
        try:
            # Shared durability kernel (no upload here, so no orphan to reclaim):
            # UPSERT the shortened list, rolling the entity back if the save fails.
            await save_photo_urls_or_rollback(
                self.profile_repo, self._current_profile, new_list,
                previous_photo_urls=self._photo_urls,
            )
        except Exception:
            loading.hide_loading(self.page)
            log.exception("AdditionalPhotos: remove failed user=%s",
                          self._current_profile.user_id)
            await show_status(self._status_banner, self._status_text,"מחיקת התמונה נכשלה. אנא נסה/י שוב.", ok=False)
            return
        # DB no longer references the file → delete it (best-effort, off-thread).
        await asyncio.to_thread(self.storage.delete_file, removed_path)
        loading.hide_loading(self.page)

        self._photo_urls = new_list
        self._refresh_photos()
        await show_status(self._status_banner, self._status_text,"התמונה הוסרה.", ok=True, auto_hide_sec=3.0)

    # ============================================================
    #  Status banner
    # ============================================================

