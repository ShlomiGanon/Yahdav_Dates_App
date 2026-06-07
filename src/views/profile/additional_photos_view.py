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
from views.common.screen import CONTENT_BODY_SPACING
from views.common.navigation import back_to_menu_button, back_button
from views.common.photos import DEFAULT_PROFILE_IMAGE, extra_photo_urls, photo_thumb
from components import loading
from components.buttons import create_primary_button, create_secondary_button
from services.I_Profile_Repository import IProfileRepository
from services.I_Storage_Service import IStorageService
from models.user_profile import UserProfile
from utils.constants import TextSizes, UIConstants, ThemeColors, StorageConfig

log = logging.getLogger(__name__)


class AdditionalPhotosView(BaseView):
    ROUTE = "/profile/photos"

    SESSION_USER_ID_KEY = "current_user_id"
    _PROFILE_ROUTE = "/profile/me"
    _THUMB_SIZE = 110

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

    def get_body(self) -> ft.Control:
        heading = ft.Text(
            "תמונות נוספות",
            size=TextSizes.H1,
            weight=ft.FontWeight.BOLD,
            color=ThemeColors.TEXT_MAIN,
            rtl=True,
            text_align=ft.TextAlign.RIGHT,
        )
        hint = ft.Text(
            f"ניתן להוסיף עד {StorageConfig.MAX_EXTRA_PHOTOS} תמונות, "
            f"בנוסף לתמונת הפרופיל הראשית.",
            size=TextSizes.SMALL,
            color=ThemeColors.TEXT_MAIN,
            rtl=True,
            text_align=ft.TextAlign.RIGHT,
        )
        self._file_picker = ft.FilePicker()
        # STRETCH so tiles span the card width and right-align via text_align.
        self._photos_area = ft.Column(
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        return ft.Column(
            controls=[heading, hint, self._photos_area],
            spacing=CONTENT_BODY_SPACING,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def get_actions(self) -> list[ft.Control]:
        # Stack-aware "back to profile" (profile is the only entry point) + the
        # menu button (UNWIND to /menu).
        return [
            back_button(
                self.page, label="חזרה לפרופיל", fallback=self._PROFILE_ROUTE,
            ),
            back_to_menu_button(self.page),
        ]

    def get_status_banner(self) -> ft.Control:
        self._status_text = ft.Text(
            value="", size=TextSizes.BODY, color=ft.Colors.WHITE,
            weight=ft.FontWeight.W_600, rtl=True, text_align=ft.TextAlign.RIGHT,
        )
        self._status_banner = ft.Container(
            content=self._status_text,
            bgcolor=ThemeColors.SUCCESS,
            padding=14,
            border_radius=UIConstants.CORNER_RADIUS,
            visible=False,
            width=UIConstants.INPUT_WIDTH,
            alignment=ft.Alignment(0, 0),
        )
        return self._status_banner

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
        current_user = self.page.session.store.get(self.SESSION_USER_ID_KEY)
        if not current_user:
            await self._show_status("אנא התחבר/י תחילה.", ok=False)
            await asyncio.sleep(1.5)
            # Route Liveness Check: don't bounce a user who already left.
            if not self._is_live():
                return
            self.page.go("/auth/login")
            return

        loading.show_loading(self.page)
        try:
            profile = await asyncio.to_thread(
                self.profile_repo.get_profile, current_user,
            )
        except Exception:
            loading.hide_loading(self.page)
            log.exception("AdditionalPhotos: load failed user=%s", current_user)
            await self._show_status("טעינת התמונות נכשלה. אנא נסה/י שוב.", ok=False)
            return
        loading.hide_loading(self.page)

        # Route Liveness Check: the fetch await yielded control; if the user
        # navigated away, abort before any navigation or page.update().
        if not self._is_live():
            return

        if profile is None:
            await self._show_status("לא נמצא פרופיל. אנא התחבר/י מחדש.", ok=False)
            await asyncio.sleep(1.5)
            self.page.go("/auth/login")
            return

        self._current_profile = profile
        self._photo_urls = list(profile.photo_urls)[:StorageConfig.MAX_PROFILE_PHOTOS]
        self._refresh_photos()
        self.page.update()

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
            height=UIConstants.BUTTON_HEIGHT,   # 70px tap target
            text_size=TextSizes.INPUT,
        )
        info = ft.Column(
            controls=[caption, remove_btn],
            spacing=8, expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        return ft.Row(
            controls=[photo_thumb(path, size=self._THUMB_SIZE), info],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    # ============================================================
    #  Handlers
    # ============================================================

    async def _on_add_photo(self, e: ft.ControlEvent) -> None:
        if self._current_profile is None:
            await self._show_status("לא ניתן להוסיף — הפרופיל לא נטען.", ok=False)
            return
        if len(self._extras()) >= StorageConfig.MAX_EXTRA_PHOTOS:
            await self._show_status(
                f"ניתן להוסיף עד {StorageConfig.MAX_EXTRA_PHOTOS} תמונות נוספות.",
                ok=False,
            )
            return
        if self._file_picker is None:
            await self._show_status("בורר הקבצים אינו זמין כעת.", ok=False)
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
            await self._show_status("פתיחת בורר הקבצים נכשלה.", ok=False)
            return
        if not files:
            return
        data = files[0].bytes
        if not data:
            await self._show_status("טעינת התמונה נכשלה. נסה/י קובץ אחר.", ok=False)
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
            self._current_profile.photo_urls = tuple(new_list)
            await asyncio.to_thread(
                self.profile_repo.save_profile, self._current_profile,
            )
        except Exception:
            loading.hide_loading(self.page)
            log.exception("AdditionalPhotos: add failed user=%s",
                          self._current_profile.user_id)
            self._current_profile.photo_urls = tuple(self._photo_urls)
            if stored_path:
                await asyncio.to_thread(self.storage.delete_file, stored_path)
            await self._show_status("שמירת התמונה נכשלה. אנא נסה/י שוב.", ok=False)
            return
        loading.hide_loading(self.page)

        self._photo_urls = new_list
        self._refresh_photos()
        await self._show_status("התמונה נוספה בהצלחה!", ok=True, auto_hide_sec=3.0)

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
            self._current_profile.photo_urls = tuple(new_list)
            await asyncio.to_thread(
                self.profile_repo.save_profile, self._current_profile,
            )
        except Exception:
            loading.hide_loading(self.page)
            log.exception("AdditionalPhotos: remove failed user=%s",
                          self._current_profile.user_id)
            self._current_profile.photo_urls = tuple(self._photo_urls)
            await self._show_status("מחיקת התמונה נכשלה. אנא נסה/י שוב.", ok=False)
            return
        # DB no longer references the file → delete it (best-effort, off-thread).
        await asyncio.to_thread(self.storage.delete_file, removed_path)
        loading.hide_loading(self.page)

        self._photo_urls = new_list
        self._refresh_photos()
        await self._show_status("התמונה הוסרה.", ok=True, auto_hide_sec=3.0)

    # ============================================================
    #  Status banner
    # ============================================================

    async def _show_status(
        self, message: str, *, ok: bool, auto_hide_sec: float = 0.0,
    ) -> None:
        if self._status_banner is None or self._status_text is None:
            return
        self._status_text.value = message
        self._status_banner.bgcolor = ThemeColors.SUCCESS if ok else ThemeColors.DANGER
        self._status_banner.visible = True
        self._status_banner.update()
        if auto_hide_sec > 0:
            await asyncio.sleep(auto_hide_sec)
            self._status_banner.visible = False
            try:
                self._status_banner.update()
            except Exception:
                pass
