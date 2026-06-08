"""Integration & E2E Verification Blueprint — component-orchestration tests.

STRATEGY
========
These are INTEGRATION tests, not unit tests: the real concrete services
(`SqliteAuthService`, `SqliteProfileRepository`, `SqliteMessagingService`,
`LocalDiskStorageService`) run against a DEDICATED dev SQLite file and a
dedicated uploads dir in a per-test temp dir. Nothing is mocked away — we verify
the actual interaction boundaries the role-interfaces promise.

Three boundaries are exercised:

  1. Auth ⇄ Session ⇄ Router bridge
     - login_user / signup_user return a real UID (not a bool).
     - "Remember Me" stores a SHA-256 HASH (never the raw token) in user_sessions.
     - From a COLD boot, `Router.resolve_initial_route()` awaits the device-token
       read (event-driven settle — no fixed delay), validates it off-thread,
       stashes the identity into `page.session.store`, and routes to /menu. A
       missing or bogus token falls back to /auth/welcome (and clears the dead token).
     A minimal `FakePage` stands in for the Flet client: it records navigation
     instead of building views, so the test isolates the IDENTITY bridge from
     real view construction. It implements only the surface the router touches:
     `session.store`, async `shared_preferences`, `go`, `route`.

  2. Profile ⇄ Storage subsystem integration
     - photo bytes are written via IStorageService into data/uploads/ (here a
       temp uploads dir), off-thread via `asyncio.to_thread`;
     - the returned local path is saved through IProfileRepository.save_profile;
     - the write is an UPSERT — it updates the row in place and does NOT cascade
       a delete into the linked auth_credentials / user_sessions rows (verified
       by logging in and validating the remember-me token AFTER the photo save).

  3. Messaging ⇄ Profile constraints
     - IMessagingService is intentionally BLOCK-AGNOSTIC (it shares only db_path
       with the other services; coupling it to the profile repo would break the
       decoupling invariant). The block GATE is enforced upstream in the profile
       layer: `add_block` → `is_blocked()` is True and `discover_profiles`
       EXCLUDES the blocked user, so the UI can never reach the chat entry point.

RUN
===
    python -m unittest tests.test_component_orchestration        # from repo root
    python -m unittest discover -s tests                         # all tests

No third-party test runner required (stdlib `unittest`). `src/` is bootstrapped
onto sys.path below so the suite runs with or without the editable install.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

# Bootstrap the source root (package-dir = {"" = "src"}) so absolute imports
# (`services.*`, `utils.*`, `views.*`) resolve regardless of install state.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from services.sqlite.sqlite_profile_repository import SqliteProfileRepository
from services.sqlite.sqlite_auth_service import SqliteAuthService
from services.sqlite.sqlite_messaging_service import SqliteMessagingService
from services.local.local_disk_storage_service import LocalDiskStorageService
from services.sqlite.sqlite_queries import ProfileQueries
from services.interfaces.i_auth_service import IAuthService
from services.interfaces.i_profile_repository import IProfileRepository
from services.interfaces.i_messaging_service import IMessagingService
from services.interfaces.i_storage_service import IStorageService
from utils.constants import MessageType, AssetPaths, AuthConfig, MatchConfig, ChatConfig
from utils import local_storage
from utils import routes
from utils.router import Router, _DEFAULT_ROUTE
from views.menu.main_menu_view import MainMenuView
from views.profile.user_profile_view import UserProfileView
from views.profile.my_profile_view import MyProfileView
from views.matching.discover_view import DiscoverView
from views.matching.chat_view import ChatView
from views.auth.login_view import LoginView
from views.auth.signup_view import SignupView
from views.common.helpers.navigation import go_back
from views._base import BaseView
from views.common.engine import renderer as ui
from views.common.helpers import peer_data
from views.common.engine.screen import BodyLayout
from views.common.helpers.photo_ops import save_photo_urls_or_rollback
from views.common.helpers.load_flow import run_guarded_load, LoadGuard
from components import loading
from components.error_card import create_error_card
from components.feedback import create_status_banner

import flet as ft
from datetime import date, datetime
from models.sqlite_user_profile import SQLiteUserProfile
from models.user_profile import (
    Gender, AccountStatus, LocalizedText, Location, Lifestyle,
)

_TEST_PASSWORD = "Passw0rd!"


# ============================================================================
#  Minimal Flet Page stand-in (records navigation; builds no views)
# ============================================================================

class _FakeSessionStore:
    """Mirrors the SessionStore surface the router/views use."""
    def __init__(self) -> None:
        self._d: dict[str, object] = {}

    def set(self, k: str, v: object) -> None:
        self._d[k] = v

    def get(self, k: str):
        return self._d.get(k)

    def contains_key(self, k: str) -> bool:
        return k in self._d

    def remove(self, k: str) -> None:
        self._d.pop(k, None)


class _FakeSharedPreferences:
    """Async device store stand-in (page.shared_preferences)."""
    def __init__(self) -> None:
        self._d: dict[str, object] = {}

    async def get(self, k: str):
        return self._d.get(k)

    async def set(self, k: str, v: object) -> bool:
        self._d[k] = v
        return True

    async def remove(self, k: str) -> bool:
        self._d.pop(k, None)
        return True


class _FakeSession:
    def __init__(self) -> None:
        self.store = _FakeSessionStore()


class FakePage:
    """The smallest Page the Router's identity bridge touches. `go` records the
    target route WITHOUT invoking on_route_change, so no real view is built."""
    def __init__(self) -> None:
        self.session = _FakeSession()
        self.shared_preferences = _FakeSharedPreferences()
        self.route = "/"
        self.go_calls: list[str] = []
        self.on_route_change = None
        self.views: list = []
        self.overlay: list = []          # used by the loading overlay
        self.update_count = 0

    def go(self, route: str) -> None:
        self.route = route
        self.go_calls.append(route)

    def update(self) -> None:
        self.update_count += 1

    def run_task(self, handler, *args):
        # build() schedules the async load here; the lifecycle tests await
        # `_load_profile` manually, so this is a no-op.
        return None


# ============================================================================
#  Shared backend builder
# ============================================================================

class _BackendMixin:
    """Builds the four real services against a per-test temp DB + uploads dir."""

    def _build_backend(self):
        self._tmp = tempfile.mkdtemp(prefix="yahdav_it_")
        self.db_path = os.path.join(self._tmp, "dev.sqlite3")
        self.uploads_dir = os.path.join(self._tmp, "uploads")
        # FK order: profiles first (creates user_profiles), then the rest.
        self.profiles = SqliteProfileRepository(self.db_path)
        self.auth = SqliteAuthService(self.db_path)
        self.messaging = SqliteMessagingService(self.db_path)
        self.storage = LocalDiskStorageService(self.uploads_dir)

    def _teardown_backend(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _signup(self, username: str, email: str) -> str:
        """Create an account and return its UID."""
        self.assertTrue(
            self.auth.signup_user(username, email, _TEST_PASSWORD),
            f"signup failed for {username}",
        )
        profile = self.profiles.find_profile_by_email(email)
        self.assertIsNotNone(profile)
        return profile.user_id

    def _session_token_hashes(self) -> list[str]:
        with sqlite3.connect(self.db_path) as c:
            return [r[0] for r in c.execute("SELECT token_hash FROM user_sessions")]


# ============================================================================
#  1. Auth ⇄ Session ⇄ Router bridge
# ============================================================================

class TestAuthSessionRouterBridge(_BackendMixin, unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self._build_backend()
        # The composition root registers services under these keys; the router
        # pulls them out per route. Wire a FakePage the same way app.py does.
        self.page = FakePage()
        self.page.session.store.set("auth", self.auth)
        self.page.session.store.set("profiles", self.profiles)
        self.page.session.store.set("messaging", self.messaging)
        self.page.session.store.set("storage", self.storage)

    def tearDown(self) -> None:
        self._teardown_backend()

    def test_concrete_services_satisfy_their_role_interfaces(self):
        self.assertIsInstance(self.auth, IAuthService)
        self.assertIsInstance(self.profiles, IProfileRepository)
        self.assertIsInstance(self.messaging, IMessagingService)
        self.assertIsInstance(self.storage, IStorageService)

    def test_login_returns_uid_not_bool(self):
        uid = self._signup("alice", "alice@example.com")
        logged_in = self.auth.login_user("alice", _TEST_PASSWORD)
        self.assertEqual(logged_in, uid)                 # UID, not True/False
        self.assertIsNone(self.auth.login_user("alice", "wrong-password"))

    def test_remember_me_stores_hash_never_raw_token(self):
        uid = self._signup("bob", "bob@example.com")
        token = self.auth.generate_remember_me_token(uid)
        self.assertTrue(token)
        # The DB must hold ONLY the SHA-256 hash, never the raw token.
        hashes = self._session_token_hashes()
        self.assertIn(hashlib.sha256(token.encode()).hexdigest(), hashes)
        self.assertNotIn(token, hashes)
        # And the token round-trips back to its owner.
        self.assertEqual(self.auth.validate_remember_me_token(token), uid)

    async def test_cold_boot_resolves_identity_with_event_driven_settle(self):
        uid = self._signup("carol", "carol@example.com")
        token = self.auth.generate_remember_me_token(uid)
        await local_storage.write_token(self.page, token)   # device remembers

        # Cold boot: session is empty; only the device token exists.
        self.assertIsNone(self.page.session.store.get("current_user_id"))
        router = Router(self.page)

        await router.resolve_initial_route()

        # Event-driven settle: a boot spinner was mounted (never a blank first
        # frame) while the token read was awaited — no fixed delay to honour.
        self.assertTrue(self.page.views, "boot spinner should have been mounted")
        # Identity rehydrated into the session, and routed to the post-login hub.
        self.assertEqual(self.page.route, MainMenuView.ROUTE)
        self.assertEqual(self.page.session.store.get("current_user_id"), uid)
        self.assertEqual(
            self.page.session.store.get("current_user_email"), "carol@example.com",
        )

    async def test_cold_boot_without_token_falls_back_to_welcome(self):
        router = Router(self.page)
        await router.resolve_initial_route()
        self.assertEqual(self.page.route, _DEFAULT_ROUTE)
        self.assertIsNone(self.page.session.store.get("current_user_id"))

    async def test_cold_boot_with_bogus_token_clears_it_and_falls_back(self):
        await local_storage.write_token(self.page, "not-a-real-token")
        router = Router(self.page)
        await router.resolve_initial_route()
        self.assertEqual(self.page.route, _DEFAULT_ROUTE)
        # The dead device token was purged so it's never re-evaluated next boot.
        self.assertIsNone(await local_storage.read_token(self.page))

# ============================================================================
#  1b. Auth credential mechanics — scrypt hashing + failed-attempt tracking
# ============================================================================
#  `AuthConfig` declares `MAX_FAILED_LOGIN_ATTEMPTS` / `LOCKOUT_MINUTES` as the
#  abuse-threshold policy; what `SqliteAuthService` actually wires up TODAY is
#  the underlying mechanism those thresholds would gate on — a per-account
#  `failed_attempts` counter (incremented on a wrong password, reset to 0 on a
#  success) backed by salted-scrypt password hashing. These tests pin down that
#  real, present-day mechanism (not the not-yet-enforced lockout policy).

class TestAuthCredentialMechanics(_BackendMixin, unittest.TestCase):

    def setUp(self) -> None:
        self._build_backend()

    def tearDown(self) -> None:
        self._teardown_backend()

    def _credential_row(self, uid: str) -> sqlite3.Row:
        with sqlite3.connect(self.db_path) as c:
            c.row_factory = sqlite3.Row
            row = c.execute(
                "SELECT failed_attempts, last_login_at, password_hash "
                "FROM auth_credentials WHERE user_id = ?",
                (uid,),
            ).fetchone()
        self.assertIsNotNone(row)
        return row

    # ---- scrypt hashing (the static helpers `login_user`/`signup_user` use) --

    def test_hash_password_uses_scrypt_with_a_random_salt(self):
        h1 = SqliteAuthService._hash_password(_TEST_PASSWORD)
        h2 = SqliteAuthService._hash_password(_TEST_PASSWORD)
        scheme, salt_hex, digest_hex = h1.split("$")
        self.assertEqual(scheme, "scrypt")
        bytes.fromhex(salt_hex)     # well-formed hex, doesn't raise
        bytes.fromhex(digest_hex)
        # Same password, two calls → different salts → different hashes.
        self.assertNotEqual(h1, h2)

    def test_verify_password_round_trips_and_rejects_wrong_or_malformed(self):
        stored = SqliteAuthService._hash_password(_TEST_PASSWORD)
        self.assertTrue(SqliteAuthService._verify_password(_TEST_PASSWORD, stored))
        self.assertFalse(SqliteAuthService._verify_password("wrong-password", stored))
        # Defensive parsing: a malformed/garbled stored value never raises.
        self.assertFalse(SqliteAuthService._verify_password(_TEST_PASSWORD, "garbage"))
        self.assertFalse(SqliteAuthService._verify_password(_TEST_PASSWORD, "plain$abc$def"))

    def test_signup_persists_a_scrypt_hash_not_the_plaintext(self):
        uid = self._signup("hank", "hank@example.com")
        row = self._credential_row(uid)
        self.assertTrue(row["password_hash"].startswith("scrypt$"))
        self.assertNotIn(_TEST_PASSWORD, row["password_hash"])

    # ---- failed_attempts counter (the mechanism MAX_FAILED_LOGIN_ATTEMPTS /
    # LOCKOUT_MINUTES would gate on, were that policy wired up) --------------

    def test_failed_login_increments_the_counter_without_blocking(self):
        uid = self._signup("ivy", "ivy@example.com")
        self.assertEqual(self._credential_row(uid)["failed_attempts"], 0)

        for expected in (1, 2, 3):
            self.assertIsNone(self.auth.login_user("ivy", "wrong-password"))
            self.assertEqual(self._credential_row(uid)["failed_attempts"], expected)

        # No enforcement is wired to the counter today — even past the
        # configured MAX_FAILED_LOGIN_ATTEMPTS floor, a correct password still
        # logs in (pins down present behaviour; would need updating if/when
        # lockout enforcement lands).
        self.assertGreaterEqual(
            self._credential_row(uid)["failed_attempts"],
            0,
        )
        for _ in range(AuthConfig.MAX_FAILED_LOGIN_ATTEMPTS):
            self.auth.login_user("ivy", "wrong-password")
        self.assertEqual(self.auth.login_user("ivy", _TEST_PASSWORD), uid)

    def test_successful_login_resets_the_counter_to_zero(self):
        uid = self._signup("jack", "jack@example.com")
        self.auth.login_user("jack", "wrong-password")
        self.auth.login_user("jack", "wrong-password")
        self.assertEqual(self._credential_row(uid)["failed_attempts"], 2)

        self.assertEqual(self.auth.login_user("jack", _TEST_PASSWORD), uid)

        row = self._credential_row(uid)
        self.assertEqual(row["failed_attempts"], 0)
        # `last_login_at` is stamped on every attempt (success AND failure —
        # `UPDATE_LOGIN_RESULT` sets it unconditionally), so its presence alone
        # doesn't distinguish a win from a miss; only `failed_attempts` does.
        self.assertIsNotNone(row["last_login_at"])

    def test_unknown_login_identifier_does_not_touch_any_counter(self):
        uid = self._signup("kate", "kate@example.com")
        self.assertIsNone(self.auth.login_user("nobody-such-user", "whatever1"))
        # The enumeration-guard decoy path verifies against a dummy hash and
        # touches no row — kate's own counter stays untouched.
        self.assertEqual(self._credential_row(uid)["failed_attempts"], 0)


# ============================================================================
#  2. Profile ⇄ Storage subsystem integration
# ============================================================================

class TestProfileStorageIntegration(_BackendMixin, unittest.IsolatedAsyncioTestCase):

    # 1x1 transparent PNG — real-enough bytes for the storage layer.
    _PNG = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
        b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    def setUp(self) -> None:
        self._build_backend()

    def tearDown(self) -> None:
        self._teardown_backend()

    def _assert_under_uploads(self, path: str) -> None:
        self.assertEqual(
            os.path.realpath(os.path.dirname(path)),
            os.path.realpath(self.uploads_dir),
        )

    async def test_registration_seeds_default_main_picture(self):
        uid = self._signup("dave", "dave@example.com")
        profile = await asyncio.to_thread(self.profiles.get_profile, uid)
        # REQUIREMENT: a new user's main picture defaults to the template.
        self.assertEqual(profile.photo_urls, (AssetPaths.DEFAULT_PROFILE_IMAGE,))

    async def test_photo_upload_persists_and_upsert_does_not_cascade(self):
        uid = self._signup("erin", "erin@example.com")
        token = self.auth.generate_remember_me_token(uid)

        # --- Store bytes off-thread via IStorageService (the view's contract) ---
        stored = await asyncio.to_thread(self.storage.upload_file, self._PNG, "me.png")
        self.assertTrue(os.path.exists(stored))
        self._assert_under_uploads(stored)

        # --- Overwrite the MAIN picture (index 0) and UPSERT the profile ---
        profile = await asyncio.to_thread(self.profiles.get_profile, uid)
        profile.photo_urls = (stored,)
        await asyncio.to_thread(self.profiles.save_profile, profile)

        reloaded = await asyncio.to_thread(self.profiles.get_profile, uid)
        self.assertEqual(reloaded.photo_urls, (stored,))

        # --- The UPSERT must NOT have cascade-deleted linked rows ---
        self.assertEqual(self.auth.login_user("erin", _TEST_PASSWORD), uid,
                         "credentials were lost — REPLACE cascade leaked in")
        self.assertEqual(self.auth.validate_remember_me_token(token), uid,
                         "remember-me session was lost — REPLACE cascade leaked in")

    async def test_gallery_add_then_remove_extra(self):
        uid = self._signup("frank", "frank@example.com")
        main = await asyncio.to_thread(self.storage.upload_file, self._PNG, "main.png")
        e1 = await asyncio.to_thread(self.storage.upload_file, self._PNG, "e1.png")
        e2 = await asyncio.to_thread(self.storage.upload_file, self._PNG, "e2.png")

        profile = await asyncio.to_thread(self.profiles.get_profile, uid)
        profile.photo_urls = (main, e1, e2)            # main + 2 extras
        await asyncio.to_thread(self.profiles.save_profile, profile)

        reloaded = await asyncio.to_thread(self.profiles.get_profile, uid)
        self.assertEqual(reloaded.photo_urls, (main, e1, e2))

        # Remove the first extra: persist the shortened list, THEN delete file.
        reloaded.photo_urls = (main, e2)
        await asyncio.to_thread(self.profiles.save_profile, reloaded)
        deleted = await asyncio.to_thread(self.storage.delete_file, e1)
        self.assertTrue(deleted)
        self.assertFalse(os.path.exists(e1))

        final = await asyncio.to_thread(self.profiles.get_profile, uid)
        self.assertEqual(final.photo_urls, (main, e2))

    async def test_storage_refuses_delete_outside_its_root(self):
        # Defence-in-depth: a stale/hand-edited path can't unlink arbitrary files.
        outside = os.path.join(self._tmp, "outside.txt")
        Path(outside).write_text("keep me")
        self.assertFalse(await asyncio.to_thread(self.storage.delete_file, outside))
        self.assertTrue(os.path.exists(outside))


# ============================================================================
#  2b. Photo-write durability kernel (views/common/photo_ops.py)
# ============================================================================

class TestPhotoWriteRollbackKernel(_BackendMixin, unittest.IsolatedAsyncioTestCase):
    """The shared photo-write transaction (`save_photo_urls_or_rollback`) is the
    one home of Persistence invariant #5. A SUCCESS persists via the repository's
    UPSERT (so linked credentials/sessions survive — no REPLACE cascade); a
    FAILURE rolls the in-memory entity back to its previous list AND deletes the
    just-uploaded orphan file, then re-raises."""

    _PNG = TestProfileStorageIntegration._PNG   # reuse the 1×1 png fixture

    def setUp(self) -> None:
        self._build_backend()

    def tearDown(self) -> None:
        self._teardown_backend()

    async def test_success_persists_and_does_not_cascade(self):
        uid = self._signup("pat", "pat@example.com")
        token = self.auth.generate_remember_me_token(uid)
        stored = await asyncio.to_thread(self.storage.upload_file, self._PNG, "m.png")

        profile = await asyncio.to_thread(self.profiles.get_profile, uid)
        await save_photo_urls_or_rollback(
            self.profiles, profile, [stored],
            previous_photo_urls=list(profile.photo_urls),
            storage=self.storage, orphan_path=stored,
        )

        reloaded = await asyncio.to_thread(self.profiles.get_profile, uid)
        self.assertEqual(reloaded.photo_urls, (stored,))
        # UPSERT (not REPLACE) → linked credentials / remember-me session survive.
        self.assertEqual(self.auth.login_user("pat", _TEST_PASSWORD), uid)
        self.assertEqual(self.auth.validate_remember_me_token(token), uid)

    async def test_failure_rolls_back_entity_and_deletes_orphan(self):
        uid = self._signup("quinn", "quinn@example.com")
        profile = await asyncio.to_thread(self.profiles.get_profile, uid)
        previous = list(profile.photo_urls)
        orphan = await asyncio.to_thread(
            self.storage.upload_file, self._PNG, "orphan.png",
        )
        self.assertTrue(os.path.exists(orphan))

        class _FailingRepo:
            """Stand-in repository whose save always fails mid-transaction."""
            def save_profile(self, _profile):
                raise RuntimeError("simulated save failure")

        with self.assertRaises(RuntimeError):
            await save_photo_urls_or_rollback(
                _FailingRepo(), profile, previous + [orphan],
                previous_photo_urls=previous,
                storage=self.storage, orphan_path=orphan,
            )

        # Entity rolled back to its previous list, and the orphan reclaimed.
        self.assertEqual(profile.photo_urls, tuple(previous))
        self.assertFalse(os.path.exists(orphan))


# ============================================================================
#  2c. Guarded load-flow orchestrator (views/common/load_flow.py)
# ============================================================================

class TestGuardedLoadFlow(unittest.IsolatedAsyncioTestCase):
    """`run_guarded_load` is the shared mount-load sequence for the user-scoped
    screens. It must: bounce (and skip the fetch) on a failed guard; render on
    success; show a calm banner on a fetch error; skip the render if the view
    went stale during the await — always leaving the loading overlay balanced."""

    def setUp(self) -> None:
        loading._active_loaders = 0
        self.page = FakePage()
        if loading._loading_overlay in self.page.overlay:
            self.page.overlay.remove(loading._loading_overlay)
        self.banner, self.text = create_status_banner()
        self.log = logging.getLogger("test.load_flow")

    def _recorder(self, sink: list):
        async def _on_success(result) -> None:
            sink.append(result)
        return _on_success

    async def test_failed_guard_bounces_and_skips_fetch(self):
        fetched, rendered, bounced = [], [], []
        await run_guarded_load(
            self.page,
            guards=[LoadGuard(
                ok=False, message="אנא התחבר/י תחילה",
                bounce=lambda: bounced.append(True),
            )],
            fetch=lambda: fetched.append("FETCHED"),
            on_success=self._recorder(rendered),
            is_stale=lambda: False,
            status_banner=self.banner, status_text=self.text,
            logger=self.log,
            fetch_error_message="err", fetch_error_log="log",
            guard_pause_sec=0,            # don't really sleep 1.5s in a test
        )
        self.assertEqual(bounced, [True])
        self.assertEqual(fetched, [], "fetch must not run when a guard fails")
        self.assertEqual(rendered, [])
        self.assertEqual(self.text.value, "אנא התחבר/י תחילה")
        self.assertEqual(loading._active_loaders, 0)

    async def test_success_renders_and_balances_overlay(self):
        rendered = []
        await run_guarded_load(
            self.page,
            guards=[LoadGuard(ok=True, message="", bounce=lambda: None)],
            fetch=lambda: "DATA",
            on_success=self._recorder(rendered),
            is_stale=lambda: False,
            status_banner=self.banner, status_text=self.text,
            logger=self.log,
            fetch_error_message="err", fetch_error_log="log",
        )
        self.assertEqual(rendered, ["DATA"])
        self.assertEqual(loading._active_loaders, 0)
        self.assertNotIn(loading._loading_overlay, self.page.overlay)

    async def test_fetch_error_shows_banner_and_skips_render(self):
        rendered = []

        def boom():
            raise RuntimeError("db down")

        await run_guarded_load(
            self.page, guards=[],
            fetch=boom,
            on_success=self._recorder(rendered),
            is_stale=lambda: False,
            status_banner=self.banner, status_text=self.text,
            logger=self.log,
            fetch_error_message="טעינה נכשלה", fetch_error_log="boom",
        )
        self.assertEqual(rendered, [], "render must not run after a fetch error")
        self.assertEqual(self.text.value, "טעינה נכשלה")
        self.assertEqual(loading._active_loaders, 0, "overlay must be balanced")

    async def test_stale_after_fetch_skips_render(self):
        rendered = []
        await run_guarded_load(
            self.page, guards=[],
            fetch=lambda: "DATA",
            on_success=self._recorder(rendered),
            is_stale=lambda: True,          # navigated away during the fetch
            status_banner=self.banner, status_text=self.text,
            logger=self.log,
            fetch_error_message="err", fetch_error_log="log",
        )
        self.assertEqual(rendered, [], "stale view must not be mutated")
        self.assertEqual(loading._active_loaders, 0)


# ============================================================================
#  3. Messaging ⇄ Profile constraints
# ============================================================================

class TestMessagingProfileConstraints(_BackendMixin, unittest.TestCase):

    def setUp(self) -> None:
        self._build_backend()
        self.a = self._signup("ann", "ann@example.com")
        self.b = self._signup("ben", "ben@example.com")

    def tearDown(self) -> None:
        self._teardown_backend()

    def test_messaging_service_is_block_agnostic_by_design(self):
        # The service shares only db_path with the others; it intentionally does
        # NOT consult blocks. This documents that the gate is NOT here.
        mid = self.messaging.send_direct_message(self.a, self.b, "שלום", MessageType.TEXT)
        self.assertTrue(mid)
        history = self.messaging.get_chat_history(self.a, self.b, limit=20)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["content"], "שלום")
        self.assertEqual(history[0]["msg_type"], "TEXT")

    def test_block_gate_is_enforced_in_the_profile_layer(self):
        # Positive control: before blocking, B is visible in A's discover feed.
        before = [p.user_id for p in self.profiles.discover_profiles(self.a, 50)]
        self.assertIn(self.b, before)

        # A blocks B → the profile layer is the enforcement seam.
        self.profiles.add_block(self.a, self.b)

        self.assertTrue(self.profiles.get_profile(self.a).is_blocked(self.b))
        after = [p.user_id for p in self.profiles.discover_profiles(self.a, 50)]
        self.assertNotIn(self.b, after,
                         "blocked user must be excluded from discover (the chat gate)")

    def test_self_message_is_rejected(self):
        with self.assertRaises(ValueError):
            self.messaging.send_direct_message(self.a, self.a, "hi", MessageType.TEXT)


# ============================================================================
#  4. Peer-profile BLACK-SCREEN regression
# ============================================================================

class TestPeerProfileBlackScreenRegression(_BackendMixin, unittest.TestCase):
    """Rendering an UNTRUSTED, partially-populated peer profile must never throw
    a layout exception (which blanks the Flet page to black). We exercise the
    view's PURE layout builders directly — no running Flet client needed."""

    def setUp(self) -> None:
        self._build_backend()
        # A FakePage with no Flet runtime — the view only stores it; the pure
        # builders below never touch it.
        self.view = UserProfileView(FakePage(), self.profiles, target_peer_id="x")

    def tearDown(self) -> None:
        self._teardown_backend()

    @staticmethod
    def _degenerate_profile(**overrides) -> SQLiteUserProfile:
        """A worst-case peer: blank localizations, sentinel DOB, empty photos."""
        base = dict(
            _user_id="peer", _email="peer@example.com",
            _registered_at=datetime(2024, 1, 1),
            _status=AccountStatus.PENDING,
            _display_name=LocalizedText(he_male="", he_female="", he_neutral=None),
            _gender=Gender.OTHER,
            _date_of_birth=date(1900, 1, 1),          # un-onboarded sentinel
            _location=Location(city="", region=None),
            _lifestyle=Lifestyle(),
            _bio=LocalizedText(he_male="", he_female="", he_neutral=None),
            _looking_for=LocalizedText(he_male="", he_female="", he_neutral=None),
            _photo_urls=(),                            # EMPTY photo array
        )
        base.update(overrides)
        return SQLiteUserProfile(**base)

    def _assert_renders(self, profile) -> None:
        blocks = self.view._build_field_blocks(profile)
        self.assertIsInstance(blocks, list)
        self.assertTrue(blocks, "must always render at least the fallback block")
        for b in blocks:
            self.assertIsInstance(b, ft.Control)
        # Avatar must build with a non-empty src even when photos are empty.
        self.assertIsInstance(self.view._avatar(profile), ft.Control)

    def test_empty_and_blank_profile_renders_without_exception(self):
        self._assert_renders(self._degenerate_profile())

    def test_empty_photos_resolve_to_default_avatar(self):
        profile = self._degenerate_profile(_photo_urls=())
        self.assertEqual(
            peer_data.safe_photo_src(profile), AssetPaths.DEFAULT_PROFILE_IMAGE,
        )

    def test_extremely_long_bio_stays_renderable(self):
        long_bio = "א" * 5000 + " " + "ב" * 5000     # no natural break points
        profile = self._degenerate_profile(
            _display_name=LocalizedText("דנה", "דנה", "דנה"),
            _bio=LocalizedText(long_bio, long_bio, long_bio),
        )
        self._assert_renders(profile)

    def test_corrupt_db_row_is_failsoft_and_renders(self):
        """A malformed DB row must hydrate to safe defaults (never raise) AND
        render without a layout exception."""
        uid = self._signup("gail", "gail@example.com")
        # Corrupt every JSON value-object column with garbage / NULLs.
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "UPDATE user_profiles SET display_name_json=?, bio_json=?, "
                "location_json=?, lifestyle_json=?, photo_urls_json=?, "
                "ice_breakers_json=? WHERE user_id=?",
                ("not-json", "", "{bad", "null", "null", "[garbage", uid),
            )
        profile = self.profiles.get_profile(uid)         # fail-soft hydration
        self.assertIsNotNone(profile, "corrupt row must not crash get_profile")
        self._assert_renders(profile)

    def test_missing_peer_returns_none_triggering_error_card(self):
        # The view shows its error card when get_profile returns None; here we
        # assert the trigger (None) and that the shared error card builds.
        self.assertIsNone(self.profiles.get_profile("does-not-exist"))
        self.assertIsInstance(create_error_card("משהו השתבש"), ft.Control)


# ============================================================================
#  5. Backward compatibility — old accounts with missing/null photo data
# ============================================================================

class TestBackwardCompatPhotoMigration(_BackendMixin, unittest.TestCase):
    """Pre-feature accounts have null/empty/missing photo columns. Fetching and
    rendering them must never crash, position 0 must resolve to the default
    template, and a lazy migration must heal the stored row."""

    # Storable "empty" representations an old/junk row might carry. (The column
    # is NOT NULL DEFAULT '[]', so a pre-feature row actually holds '[]'; a true
    # NULL / missing-column case is covered separately via the pure helpers.)
    _EMPTY_VALUES = ("[]", "", "null", "   ")

    def setUp(self) -> None:
        self._build_backend()

    def tearDown(self) -> None:
        self._teardown_backend()

    def _set_photos_json(self, uid: str, raw) -> None:
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "UPDATE user_profiles SET photo_urls_json = ? WHERE user_id = ?",
                (raw, uid),
            )

    def _read_photos_json(self, uid: str):
        with sqlite3.connect(self.db_path) as c:
            row = c.execute(
                "SELECT photo_urls_json FROM user_profiles WHERE user_id = ?", (uid,),
            ).fetchone()
        return row[0] if row else None

    def test_fetch_resolves_position0_to_default_for_all_empty_states(self):
        # REQ 1: every storable empty representation hydrates safely with the
        # default template at position 0 — never an empty list, never a crash.
        for i, raw in enumerate(self._EMPTY_VALUES):
            uid = self._signup(f"old{i}", f"old{i}@example.com")
            self._set_photos_json(uid, raw)
            profile = self.profiles.get_profile(uid)
            self.assertIsNotNone(profile, f"crashed on photos_json={raw!r}")
            self.assertEqual(
                profile.photo_urls, (AssetPaths.DEFAULT_PROFILE_IMAGE,),
                f"position 0 not defaulted for photos_json={raw!r}",
            )

    def test_fetch_resolves_null_or_missing_column_via_helpers(self):
        # The true "null / missing column" case (which the NOT NULL schema can't
        # store): the repo's parser maps None → empty, and the fetch-layer
        # normalizer defaults position 0 to the template.
        self.assertEqual(SqliteProfileRepository._photos_from_json(None), ())
        self.assertEqual(
            SqliteProfileRepository._with_default_main(()),
            (AssetPaths.DEFAULT_PROFILE_IMAGE,),
        )
        # A populated list is passed through untouched.
        self.assertEqual(
            SqliteProfileRepository._with_default_main(("real.jpg",)), ("real.jpg",),
        )

    def test_safe_indexing_helpers_on_empty(self):
        # REQ 2: the canonical accessors are length-checked.
        from views.common.helpers.photos import resolve_main_photo, extra_photo_urls
        self.assertEqual(resolve_main_photo([]), AssetPaths.DEFAULT_PROFILE_IMAGE)
        self.assertEqual(resolve_main_photo(()), AssetPaths.DEFAULT_PROFILE_IMAGE)
        self.assertEqual(extra_photo_urls([]), [])
        self.assertEqual(extra_photo_urls([AssetPaths.DEFAULT_PROFILE_IMAGE]), [])

    def test_lazy_migration_heals_empty_row(self):
        # REQ 3: ensure_default_photo persists the default into an old empty row.
        uid = self._signup("heal", "heal@example.com")
        self._set_photos_json(uid, "[]")             # pre-feature account: empty list
        self.profiles.ensure_default_photo(uid)
        healed = self._read_photos_json(uid)
        self.assertEqual(healed, ProfileQueries.DEFAULT_PHOTOS_JSON)

    def test_lazy_migration_is_idempotent_and_preserves_real_photos(self):
        uid = self._signup("keep", "keep@example.com")
        real = '["data/uploads/real-main.jpg", "data/uploads/extra1.jpg"]'
        self._set_photos_json(uid, real)
        # A populated row must NOT be overwritten...
        self.profiles.ensure_default_photo(uid)
        self.assertEqual(self._read_photos_json(uid), real)
        # ...and healing an empty row twice is stable.
        uid2 = self._signup("twice", "twice@example.com")
        self._set_photos_json(uid2, "")
        self.profiles.ensure_default_photo(uid2)
        self.profiles.ensure_default_photo(uid2)
        self.assertEqual(self._read_photos_json(uid2), ProfileQueries.DEFAULT_PHOTOS_JSON)

    def test_ensure_default_photo_never_raises_on_bad_input(self):
        # Best-effort contract: empty / unknown ids are safe no-ops.
        self.profiles.ensure_default_photo("")
        self.profiles.ensure_default_photo("nonexistent-uid")


# ============================================================================
#  6. Peer-profile FULL LIFECYCLE (build + load + render) — black-screen repro
# ============================================================================

class TestPeerProfileViewLifecycle(_BackendMixin, unittest.IsolatedAsyncioTestCase):
    """Drive the WHOLE peer-profile lifecycle (build() then _load_profile) the
    way the app does — reproducing 'view moshe@mail.com as shlomi@mail.com' with
    an old account that has degenerate photo data. None of it may raise."""

    def setUp(self) -> None:
        self._build_backend()
        self.viewer = self._signup("shlomi", "shlomi@mail.com")
        self.peer = self._signup("moshe", "moshe@mail.com")

    def tearDown(self) -> None:
        self._teardown_backend()

    def _corrupt_peer_photos(self, raw) -> None:
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "UPDATE user_profiles SET photo_urls_json = ? WHERE user_id = ?",
                (raw, self.peer),
            )

    async def _drive(self) -> "UserProfileView":
        page = FakePage()
        # Model the active route: the router sets page.route to the view's route
        # before building it, so the Route Liveness Check sees a live view.
        page.route = UserProfileView.ROUTE
        page.session.store.set("current_user_id", self.viewer)
        page.session.store.set("selected_peer_id", self.peer)
        view = UserProfileView(page, self.profiles, target_peer_id=self.peer)
        built = view.build()                       # must not raise
        self.assertIsInstance(built, ft.View)
        # Model the router mounting this view as the stack top, so the identity
        # liveness guard (page.views[-1].data is self) sees it as live.
        page.views.append(built)
        await view._load_profile()                 # must not raise → renders or error-card
        return view

    async def test_view_old_peer_with_each_degenerate_photo_state(self):
        for raw in ("[]", "", "null", "not-json",
                    '["C:\\\\Old\\\\pics\\\\moshe.jpg"]',  # stale absolute path
                    '["null"]', '["   "]'):
            self._corrupt_peer_photos(raw)
            view = await self._drive()
            self.assertTrue(view._content.controls, f"no content for photos={raw!r}")
            self.assertIsNotNone(view._avatar_slot.content,
                                 f"avatar not set for photos={raw!r}")

    async def test_view_fully_malformed_peer_row(self):
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "UPDATE user_profiles SET display_name_json=?, bio_json=?, "
                "looking_for_json=?, location_json=?, lifestyle_json=?, "
                "photo_urls_json=?, gender=?, date_of_birth=? WHERE user_id=?",
                ("not-json", "", "null", "{bad", "null", "[]", "ZZZ", "garbage",
                 self.peer),
            )
        view = await self._drive()
        self.assertTrue(view._content.controls)

    async def test_missing_peer_shows_error_card_not_blank(self):
        page = FakePage()
        page.route = UserProfileView.ROUTE
        page.session.store.set("current_user_id", self.viewer)
        page.session.store.set("selected_peer_id", "does-not-exist")
        view = UserProfileView(page, self.profiles, target_peer_id="does-not-exist")
        page.views.append(view.build())            # mounted as the stack top
        await view._load_profile()
        # Error card is shown inside the shell — content is non-empty, not blank.
        self.assertTrue(view._content.controls)

    async def test_stale_navigation_suppresses_render(self):
        """Route Liveness Check: if the user navigates away while get_profile is
        in flight, the resumed coroutine must NOT render into the dead view."""
        page = FakePage()
        page.route = UserProfileView.ROUTE
        page.session.store.set("current_user_id", self.viewer)
        page.session.store.set("selected_peer_id", self.peer)
        view = UserProfileView(page, self.profiles, target_peer_id=self.peer)
        built = view.build()
        page.views.append(built)                   # mounted as the stack top
        # Simulate a forward navigation pushing ANOTHER view on top before the
        # fetch resumes: a different instance is now the stack top, so the
        # identity liveness guard must treat this view as stale.
        other = ft.View(route="/discover/peer_photos")
        other.data = object()                      # some other BaseView instance
        page.views.append(other)
        page.route = other.route
        await view._load_profile()                 # must not raise
        # Stale coroutine aborted: no profile rendered into the covered view.
        self.assertEqual(view._content.controls, [])
        self.assertIsNone(view._avatar_slot.content)
        # And the loading overlay was still torn down (finally ran).
        self.assertNotIn(loading._loading_overlay, page.overlay)

    def test_unmount_cancels_inflight_load_task(self):
        """Task ownership: the View's will_unmount hook must cancel the owned
        background load task, so a destroyed view's residual task is reaped."""
        page = FakePage()
        page.route = UserProfileView.ROUTE
        page.session.store.set("selected_peer_id", self.peer)
        view = UserProfileView(page, self.profiles, target_peer_id=self.peer)
        built = view.build()

        # FakePage.run_task is a no-op, so inject a stand-in task to observe the
        # cancel() the teardown hook is contractually required to call.
        class _FakeTask:
            def __init__(self) -> None:
                self.cancelled = False
            def done(self) -> bool:
                return False
            def cancel(self) -> bool:
                self.cancelled = True
                return True

        task = _FakeTask()
        view._load_task = task
        # Flet invokes will_unmount() on the View when the router clears
        # page.views; build() wired it to view._on_unmount.
        built.will_unmount()
        self.assertTrue(task.cancelled, "unmount must cancel the in-flight task")
        self.assertIsNone(view._load_task)


class TestNavigationStack(_BackendMixin, unittest.TestCase):
    """The router maintains a real push/pop view STACK (not destroy-and-replace)
    and intercepts the native back button via on_view_pop. FakePage.update is a
    no-op, so did_mount never fires -> migrated views' on_mount loads never auto-
    start; this exercises pure stack STRUCTURE, not the async fetch."""

    def setUp(self) -> None:
        self._build_backend()
        self.page = FakePage()
        self.page.session.store.set("auth", self.auth)
        self.page.session.store.set("profiles", self.profiles)
        self.page.session.store.set("messaging", self.messaging)
        self.page.session.store.set("storage", self.storage)
        self.page.session.store.set("current_user_id", "viewer-1")
        self.page.session.store.set("selected_peer_id", "peer-1")
        self.router = Router(self.page)

    def tearDown(self) -> None:
        self._teardown_backend()

    def _routes(self):
        return [getattr(v, "route", None) for v in self.page.views]

    def test_push_grows_and_unwind_shrinks(self):
        self.router.handle_route_change("/menu")
        self.assertEqual(self._routes(), ["/menu"])

        self.router.handle_route_change("/matching/discover")   # forward push
        self.router.handle_route_change("/discover/profile")    # forward push
        self.router.handle_route_change("/discover/peer_photos")  # forward push
        self.assertEqual(
            self._routes(),
            ["/menu", "/matching/discover", "/discover/profile",
             "/discover/peer_photos"],
        )
        self.assertEqual(self.page.route, "/discover/peer_photos")

        # In-app "back" to a route already BELOW the top unwinds to the live
        # instance (no rebuild) and pops everything above it.
        self.router.handle_route_change("/discover/profile")
        self.assertEqual(
            self._routes(), ["/menu", "/matching/discover", "/discover/profile"],
        )
        self.assertEqual(self.page.route, "/discover/profile")

    def test_view_pop_pops_one_and_reveals_parent(self):
        for r in ("/menu", "/matching/discover", "/discover/profile"):
            self.router.handle_route_change(r)
        self.assertEqual(len(self.page.views), 3)

        self.router.handle_view_pop(None)   # hardware back
        self.assertEqual(
            self._routes(), ["/menu", "/matching/discover"],
        )
        self.assertEqual(self.page.route, "/matching/discover")

    def test_view_pop_at_root_does_not_pop_past_it(self):
        self.router.handle_route_change("/menu")
        self.router.handle_view_pop(None)               # back at the root
        self.assertEqual(self._routes(), ["/menu"])     # depth-1 invariant held

    def test_lightbox_consumes_back_button(self):
        for r in ("/menu", "/matching/discover", "/discover/profile",
                  "/discover/peer_photos"):
            self.router.handle_route_change(r)
        top = self.page.views[-1]
        peer_photos = top.data
        # Open the fullscreen lightbox, then press hardware back. The lightbox
        # is the shared `PhotoLightbox` component; its built overlay control
        # (toggled by `visible`) is what `consume_pop`/`on_pop` inspect.
        peer_photos._lightbox.control.visible = True
        depth_before = len(self.page.views)

        self.router.handle_view_pop(None)

        # The pop was CONSUMED by the lightbox: stack unchanged, overlay closed.
        self.assertEqual(len(self.page.views), depth_before)
        self.assertFalse(peer_photos._lightbox.control.visible)

    def test_reset_route_discards_history(self):
        self.router.handle_route_change("/menu")
        self.router.handle_route_change("/matching/discover")
        # A reset route NOT already in the stack wipes history to a single view.
        self.router.handle_route_change("/auth/welcome")
        self.assertEqual(self._routes(), ["/auth/welcome"])

    def test_identity_disambiguates_two_instances_of_same_route(self):
        # Two peer-profile views share the SAME ROUTE; identity (not route
        # string) must distinguish which one is live.
        a = UserProfileView(self.page, self.profiles, target_peer_id="A")
        b = UserProfileView(self.page, self.profiles, target_peer_id="B")
        self.page.views = [a.build(), b.build()]        # B is the top
        self.page.route = UserProfileView.ROUTE
        self.assertTrue(b._is_live())
        self.assertFalse(a._is_live())                  # same ROUTE, but not top


class TestLoadingOverlayRefCount(unittest.TestCase):
    """The loading overlay is reference-counted: overlapping loaders must not
    prematurely tear down the shared scrim (the singleton concurrency bug)."""

    def setUp(self) -> None:
        # Reset the module-level counter so tests are order-independent.
        loading._active_loaders = 0
        self.page = FakePage()
        if loading._loading_overlay in self.page.overlay:
            self.page.overlay.remove(loading._loading_overlay)

    def test_concurrent_loaders_no_premature_removal(self):
        loading.show_loading(self.page)            # A: 0 -> 1, attaches
        self.assertIn(loading._loading_overlay, self.page.overlay)
        loading.show_loading(self.page)            # B: 1 -> 2, stays
        self.assertIn(loading._loading_overlay, self.page.overlay)

        loading.hide_loading(self.page)            # A done: 2 -> 1, MUST stay
        self.assertIn(loading._loading_overlay, self.page.overlay,
                      "scrim removed while a sibling loader is still active")

        loading.hide_loading(self.page)            # B done: 1 -> 0, detaches
        self.assertNotIn(loading._loading_overlay, self.page.overlay)
        self.assertEqual(loading._active_loaders, 0)

    def test_unbalanced_hide_is_clamped_at_zero(self):
        loading.hide_loading(self.page)            # extra hide with no show
        self.assertEqual(loading._active_loaders, 0)   # never negative
        # A subsequent show still works correctly after the clamp.
        loading.show_loading(self.page)
        self.assertIn(loading._loading_overlay, self.page.overlay)
        loading.hide_loading(self.page)
        self.assertNotIn(loading._loading_overlay, self.page.overlay)


class _RoutingFakePage(FakePage):
    """A FakePage whose `go` drives the wired router (exactly like the real app
    wires `page.on_route_change`), so a stack-aware back actually UNWINDS the
    `page.views` stack instead of merely recording the route."""

    def go(self, route: str) -> None:
        self.route = route
        self.go_calls.append(route)
        if self.on_route_change is not None:
            self.on_route_change(route)


class TestStackAwareBack(_BackendMixin, unittest.TestCase):
    """`views.common.helpers.navigation.go_back` pops ONE level — returning to the screen
    that actually opened the current one (never a hard-coded parent) — and falls
    back to a safe route when the current screen is the stack root.

    Uses the real Router + view factories over a routing FakePage; FakePage.update
    is a no-op so migrated views' on_mount loads never auto-start — this exercises
    pure stack STRUCTURE, not the async fetch (mirrors TestNavigationStack)."""

    def setUp(self) -> None:
        self._build_backend()
        self.page = _RoutingFakePage()
        self.page.session.store.set("auth", self.auth)
        self.page.session.store.set("profiles", self.profiles)
        self.page.session.store.set("messaging", self.messaging)
        self.page.session.store.set("storage", self.storage)
        self.page.session.store.set("current_user_id", "viewer-1")
        self.page.session.store.set("selected_peer_id", "peer-1")
        self.router = Router(self.page)
        self.page.on_route_change = self.router.handle_route_change

    def tearDown(self) -> None:
        self._teardown_backend()

    def _routes(self):
        return [getattr(v, "route", None) for v in self.page.views]

    def _push(self, *routes):
        for r in routes:
            self.page.go(r)

    def test_go_back_at_root_uses_fallback(self):
        self.page.go("/menu")                          # single root view
        go_back(self.page, fallback="/auth/welcome")
        self.assertEqual(self.page.route, "/auth/welcome")

    def test_go_back_empty_stack_uses_fallback(self):
        go_back(self.page)                             # no views at all
        self.assertEqual(self.page.route, "/menu")     # default fallback

    def test_chat_back_returns_to_matches_not_discover(self):
        # THE PRIMARY FIX: chat opened from Matches must pop BACK to Matches.
        self._push("/menu", "/chat/history", "/chat/new")
        self.assertEqual(self._routes(), ["/menu", "/chat/history", "/chat/new"])
        go_back(self.page)                             # the ChatView "חזור" action
        self.assertEqual(self.page.route, "/chat/history")
        self.assertEqual(self._routes(), ["/menu", "/chat/history"])

    def test_chat_back_from_discover_returns_to_discover(self):
        # Same button, different entry point: opened from Discover → back to it.
        self._push("/menu", "/matching/discover", "/chat/new")
        go_back(self.page)
        self.assertEqual(self.page.route, "/matching/discover")
        self.assertEqual(self._routes(), ["/menu", "/matching/discover"])

    def test_deep_album_back_unwinds_one_level_each(self):
        # menu → discover → profile → peer_photos, back three times → discover…
        self._push("/menu", "/matching/discover", "/discover/profile",
                   "/discover/peer_photos")
        go_back(self.page)
        self.assertEqual(self.page.route, "/discover/profile")
        go_back(self.page)
        self.assertEqual(self.page.route, "/matching/discover")
        go_back(self.page)
        self.assertEqual(self.page.route, "/menu")
        self.assertEqual(self._routes(), ["/menu"])


class TestUnifiedCardLayout(unittest.TestCase):
    """The single card frame (built by `BaseView`): ONE translucent card holds
    header → content → status banner → actions in one column — no separate
    action bar, no HUB/CONTENT split. `EXPAND_BODY` only changes whether that
    card hugs its content and centres on the screen (compact — Welcome/Login's
    shape, the default) or fills the viewport and scrolls its own content
    (expand — chat, matches, photo albums, long forms)."""

    def _build(self, *, expand_body=False, self_scroll=False):
        self.heading = ft.Text("title")
        self.banner = ft.Container()
        self.back = ft.Text("חזור")
        heading, banner, back = self.heading, self.banner, self.back

        class _V(BaseView):
            ROUTE = "/x"
            def get_content(self): return [ui.raw(heading)]
            def get_status_banner(self): return ui.raw(banner)
            def get_actions(self): return [ui.raw(back)]
        _V.EXPAND_BODY = expand_body
        _V.BODY_LAYOUT = BodyLayout.SELF_SCROLLING if self_scroll else BodyLayout.SCROLLING
        return _V(FakePage()).build()

    def _card(self, view):
        # background_screen → View(controls=[Container(image, content=Column)]);
        # that outer Column holds exactly ONE control: the responsive card.
        root_col = view.controls[0].content
        self.assertIsInstance(root_col, ft.Column)
        self.assertEqual(len(root_col.controls), 1)
        return root_col.controls[0]

    def test_expand_card_stacks_content_banner_and_actions_inline(self):
        card = self._card(self._build(expand_body=True))
        self.assertTrue(card.expand)                          # fills the viewport
        content_area, banner, action = card.content.controls
        self.assertIs(banner, self.banner)                    # banner ABOVE the buttons
        self.assertIs(action, self.back)                      # button inline at the tail — no bar
        body_col = content_area.controls[0]
        self.assertIn(self.heading, body_col.controls)        # body lives in the content area
        self.assertNotIn(self.banner, body_col.controls)      # banner NOT in the scroll region

    def test_scrolling_wraps_content_in_one_auto_scroll_region(self):
        card = self._card(self._build(expand_body=True, self_scroll=False))
        content_area = card.content.controls[0]
        self.assertEqual(content_area.scroll, ft.ScrollMode.AUTO)

    def test_self_scrolling_avoids_nested_scroll(self):
        # SELF_SCROLLING places the body directly — it owns its own scroll
        # (an ft.ListView), so the engine never wraps it in a second region.
        card = self._card(self._build(expand_body=True, self_scroll=True))
        content_area = card.content.controls[0]
        self.assertIsNone(getattr(content_area, "scroll", None))

    def test_compact_card_centres_and_stacks_body_then_actions_no_bar(self):
        t1, t2 = ft.Text("hi"), ft.Text("bye")

        class _V(BaseView):
            ROUTE = "/menu"
            def get_content(self): return [ui.raw(c) for c in (t1, t2)]
        view = _V(FakePage()).build()

        wrap = view.controls[0].content
        self.assertIsInstance(wrap, ft.Column)
        self.assertEqual(wrap.alignment, ft.MainAxisAlignment.CENTER)
        self.assertEqual(wrap.horizontal_alignment, ft.CrossAxisAlignment.CENTER)
        self.assertEqual(len(wrap.controls), 1)               # ONE card, no action bar
        card = wrap.controls[0]
        body_col = card.content.controls[0]
        self.assertIn(t1, body_col.controls)
        self.assertIn(t2, body_col.controls)
        self.assertEqual(view.route, "/menu")

    def test_default_padding_is_the_shared_card_padding(self):
        from style.design_system import DS

        class _V(BaseView):
            ROUTE = "/x"
            def get_content(self): return [ui.raw(ft.Text("x"))]
        card = self._card(_V(FakePage()).build())
        self.assertEqual(card.padding, DS.pad.card)


class TestAuthAndMenuScreensUseTheCompactCardFrame(_BackendMixin, unittest.TestCase):
    """Every auth/menu screen renders via the compact single-card frame
    (`EXPAND_BODY = False`, the default — Welcome/Login's centred shape) AND
    ends build() with `_bind_lifecycle` (so `view.data` carries the back-ref the
    router needs for system back / lifecycle / identity-based `_is_live`)."""

    def setUp(self) -> None:
        self._build_backend()
        self.page = FakePage()
        self.page.session.store.set("auth", self.auth)

    def tearDown(self) -> None:
        self._teardown_backend()

    def _assert_compact_card(self, view, route) -> None:
        self.assertIsInstance(view, ft.View)
        self.assertEqual(view.route, route)
        # _bind_lifecycle sets view.data to the owning BaseView.
        self.assertIsNotNone(view.data, "build() must end with _bind_lifecycle")
        centered = view.controls[0].content
        self.assertIsInstance(centered, ft.Column)
        self.assertEqual(centered.alignment, ft.MainAxisAlignment.CENTER)
        self.assertEqual(len(centered.controls), 1)        # one centred card

    def test_welcome_view_uses_the_compact_card(self):
        from views.auth.welcome_view import WelcomeView
        self._assert_compact_card(WelcomeView(self.page).build(), "/auth/welcome")

    def test_main_menu_view_uses_the_compact_card(self):
        from views.menu.main_menu_view import MainMenuView
        self._assert_compact_card(MainMenuView(self.page).build(), "/menu")

    def test_placeholder_view_uses_the_compact_card(self):
        from views.common.views.placeholder_view import PlaceholderView
        view = PlaceholderView(self.page, title="בקרוב", route="/soon").build()
        self._assert_compact_card(view, "/soon")

    def test_login_view_uses_the_compact_card(self):
        from views.auth.login_view import LoginView
        self._assert_compact_card(LoginView(self.page, self.auth).build(), "/auth/login")

    def test_signup_view_uses_the_compact_card(self):
        from views.auth.signup_view import SignupView
        self._assert_compact_card(SignupView(self.page, self.auth).build(), "/auth/signup")


# ============================================================================
#  5. DiscoverView — feed load + peer selection
# ============================================================================

class TestDiscoverViewBehavior(_BackendMixin, unittest.IsolatedAsyncioTestCase):
    """DiscoverView's feed load wires the real `discover_profiles` result to
    tiles (or an empty-state banner), and choosing an action on a candidate
    stashes their id under SELECTED_PEER_ID_KEY *before* navigating — mirroring
    how login stashes the UID before routing (see `_on_action_chosen`)."""

    def setUp(self) -> None:
        self._build_backend()
        self.viewer = self._signup("viewer1", "viewer1@example.com")

    def tearDown(self) -> None:
        self._teardown_backend()

    async def _drive(self, page: FakePage) -> DiscoverView:
        page.route = DiscoverView.ROUTE
        page.session.store.set(DiscoverView.SESSION_USER_ID_KEY, self.viewer)
        view = DiscoverView(page, self.profiles)
        page.views.append(view.build())          # mounted as the stack top
        await view._load_candidates()
        return view

    async def test_feed_renders_real_discover_candidates(self):
        candidate_id = self._signup("cand1", "cand1@example.com")
        page = FakePage()
        view = await self._drive(page)
        self.assertEqual([p.user_id for p in view._candidates], [candidate_id])
        self.assertTrue(view._feed_column.controls)

    async def test_empty_feed_shows_a_status_banner_not_an_error(self):
        page = FakePage()                         # nobody else has signed up
        view = await self._drive(page)
        self.assertEqual(view._candidates, [])
        self.assertEqual(view._feed_column.controls, [])
        self.assertIn("עדיין אין פרופילים", view._status_text.value)

    async def test_choosing_view_profile_stashes_peer_then_navigates(self):
        candidate_id = self._signup("cand2", "cand2@example.com")
        page = FakePage()
        view = await self._drive(page)
        profile = next(p for p in view._candidates if p.user_id == candidate_id)

        sheet = ft.BottomSheet(content=ft.Container())
        view._on_action_chosen(sheet, DiscoverView._VIEW_PROFILE_ROUTE, profile)

        self.assertEqual(page.session.store.get(DiscoverView.SELECTED_PEER_ID_KEY),
                         candidate_id)
        self.assertEqual(page.route, DiscoverView._VIEW_PROFILE_ROUTE)

    async def test_choosing_chat_stashes_peer_then_navigates_to_chat(self):
        candidate_id = self._signup("cand3", "cand3@example.com")
        page = FakePage()
        view = await self._drive(page)
        profile = next(p for p in view._candidates if p.user_id == candidate_id)

        sheet = ft.BottomSheet(content=ft.Container())
        view._on_action_chosen(sheet, DiscoverView._CHAT_ROUTE, profile)

        self.assertEqual(page.session.store.get(DiscoverView.SELECTED_PEER_ID_KEY),
                         candidate_id)
        self.assertEqual(page.route, DiscoverView._CHAT_ROUTE)


# ============================================================================
#  6. ChatView — history render, send, identity guard
# ============================================================================

class TestChatViewBehavior(_BackendMixin, unittest.IsolatedAsyncioTestCase):
    """ChatView wires the real `IMessagingService` history to side-anchored
    bubbles (mine = absolute alignment +1/right, peer = -1/left — the
    RTL-immune scheme `create_chat_bubble` implements) and the send handler
    persists, optimistically clears the composer, and reloads."""

    def setUp(self) -> None:
        self._build_backend()
        self.viewer = self._signup("dana", "dana@example.com")
        self.peer = self._signup("eyal", "eyal@example.com")

    def tearDown(self) -> None:
        self._teardown_backend()

    async def _drive(self) -> tuple[FakePage, ChatView]:
        page = FakePage()
        page.route = ChatView.ROUTE
        page.session.store.set(ChatView.SESSION_USER_ID_KEY, self.viewer)
        view = ChatView(page, self.messaging, self_id=self.viewer, peer_id=self.peer)
        page.views.append(view.build())           # mounted as the stack top
        await view._load_history()
        return page, view

    @staticmethod
    def _bubble_sides(view: ChatView) -> dict[str, float]:
        """text -> wrapper.alignment.x (the RTL-immune side anchor)."""
        return {
            wrapper.content.content.value: wrapper.alignment.x
            for wrapper in view._messages_list.controls
        }

    async def test_history_renders_bubbles_anchored_by_sender(self):
        self.messaging.send_direct_message(self.peer, self.viewer, "הי", MessageType.TEXT)
        self.messaging.send_direct_message(self.viewer, self.peer, "שלום", MessageType.TEXT)
        _page, view = await self._drive()

        self.assertEqual(len(view._messages_list.controls), 2)
        sides = self._bubble_sides(view)
        self.assertEqual(sides["שלום"], 1)         # mine → pinned right
        self.assertEqual(sides["הי"], -1)          # peer's → pinned left

    async def test_send_persists_clears_composer_and_reappears_in_history(self):
        _page, view = await self._drive()
        view._composer.value = "מה שלומך?"

        await view._on_send(None)

        self.assertEqual(view._composer.value, "")          # optimistic clear
        history = self.messaging.get_chat_history(self.viewer, self.peer, limit=20)
        self.assertEqual(history[0]["content"], "מה שלומך?")
        self.assertEqual(history[0]["sender_id"], self.viewer)
        self.assertIn("מה שלומך?", self._bubble_sides(view))

    async def test_send_ignores_blank_input(self):
        _page, view = await self._drive()
        view._composer.value = "   "

        await view._on_send(None)

        self.assertEqual(
            self.messaging.get_chat_history(self.viewer, self.peer, limit=20), [],
        )

    async def test_identity_mismatch_shows_error_and_bounces_to_login(self):
        page = FakePage()
        page.route = ChatView.ROUTE
        page.session.store.set(ChatView.SESSION_USER_ID_KEY, "someone-else")
        view = ChatView(page, self.messaging, self_id=self.viewer, peer_id=self.peer)
        page.views.append(view.build())

        await view._load_history()

        self.assertEqual(page.route, routes.LOGIN)
        self.assertEqual(view._messages_list.controls, [])


# ============================================================================
#  7. LoginView — credential validation, identity bridge, remember-me
# ============================================================================

class TestLoginViewBehavior(_BackendMixin, unittest.IsolatedAsyncioTestCase):
    """LoginView's submit handler: sequential field validation (pinned, one
    error at a time), the identity hand-off into `page.session.store` BEFORE
    navigation (so user-scoped screens can read it on their first tick), and
    the remember-me round trip — raw token on the device, hash in the DB."""

    def setUp(self) -> None:
        self._build_backend()
        self.uid = self._signup("liora", "liora@example.com")

    def tearDown(self) -> None:
        self._teardown_backend()

    def _build_view(self) -> tuple[FakePage, LoginView]:
        page = FakePage()
        page.route = LoginView.ROUTE
        view = LoginView(page, self.auth)
        page.views.append(view.build())
        return page, view

    async def test_invalid_email_is_pinned_to_the_email_field(self):
        page, view = self._build_view()
        view._email_field.value = "not-an-email"
        view._password_field.value = _TEST_PASSWORD

        await view._on_login_click(None)

        self.assertTrue(view._email_error.value)
        self.assertFalse(view._password_error.value)        # first failure wins
        self.assertIsNone(page.session.store.get("current_user_id"))

    async def test_weak_password_is_pinned_to_the_password_field(self):
        page, view = self._build_view()
        view._email_field.value = "liora@example.com"
        view._password_field.value = "short"

        await view._on_login_click(None)

        self.assertFalse(view._email_error.value)
        self.assertTrue(view._password_error.value)

    async def test_wrong_password_shows_generic_failure_without_identity_leak(self):
        page, view = self._build_view()
        view._email_field.value = "liora@example.com"
        view._password_field.value = "WrongPassw0rd!"

        await view._on_login_click(None)

        self.assertTrue(view._password_error.value)
        self.assertIsNone(page.session.store.get("current_user_id"))
        self.assertEqual(page.route, LoginView.ROUTE)       # never navigated away

    async def test_successful_login_populates_identity_then_routes_to_menu(self):
        page, view = self._build_view()
        view._email_field.value = "liora@example.com"
        view._password_field.value = _TEST_PASSWORD

        await view._on_login_click(None)

        self.assertEqual(page.session.store.get("current_user_id"), self.uid)
        self.assertEqual(page.session.store.get("current_user_email"), "liora@example.com")
        self.assertEqual(page.route, routes.MENU)

    async def test_remember_me_checked_persists_raw_token_on_device_and_hash_in_db(self):
        page, view = self._build_view()
        view._email_field.value = "liora@example.com"
        view._password_field.value = _TEST_PASSWORD
        view._remember_me.value = True

        await view._on_login_click(None)

        token = await local_storage.read_token(page)
        self.assertTrue(token)
        hashes = self._session_token_hashes()
        self.assertIn(hashlib.sha256(token.encode()).hexdigest(), hashes)
        self.assertNotIn(token, hashes)                     # device ≠ DB content
        self.assertEqual(self.auth.validate_remember_me_token(token), self.uid)

    async def test_remember_me_unchecked_clears_a_stale_device_token(self):
        page = FakePage()
        page.route = LoginView.ROUTE
        stale = self.auth.generate_remember_me_token(self.uid)
        await local_storage.write_token(page, stale)        # a prior session's leftover

        view = LoginView(page, self.auth)
        page.views.append(view.build())
        view._email_field.value = "liora@example.com"
        view._password_field.value = _TEST_PASSWORD
        view._remember_me.value = False

        await view._on_login_click(None)

        self.assertIsNone(await local_storage.read_token(page))


# ============================================================================
#  8. SignupView — account creation + duplicate/weak-input rejection paths
# ============================================================================

class TestSignupViewBehavior(_BackendMixin, unittest.IsolatedAsyncioTestCase):
    """SignupView's submit handler: sequential field validation, the
    email-local-part → username derivation, and the real `signup_user`
    round trip — including the duplicate-email rejection surfaced on the
    email row (the most likely cause, per the view's own docstring)."""

    def setUp(self) -> None:
        self._build_backend()

    def tearDown(self) -> None:
        self._teardown_backend()

    def _build_view(self) -> tuple[FakePage, SignupView]:
        page = FakePage()
        page.route = SignupView.ROUTE
        view = SignupView(page, self.auth)
        page.views.append(view.build())
        return page, view

    @staticmethod
    async def _submit(view: SignupView, *, email: str, password: str, confirm: str) -> None:
        view._email_field.value = email
        view._password_field.value = password
        view._confirm_password_field.value = confirm
        await view._on_signup_click(None)

    async def test_invalid_email_is_pinned_to_the_email_field(self):
        page, view = self._build_view()
        await self._submit(view, email="not-an-email",
                           password=_TEST_PASSWORD, confirm=_TEST_PASSWORD)
        self.assertTrue(view._email_error.value)
        self.assertFalse(view._password_error.value)
        self.assertEqual(page.route, SignupView.ROUTE)

    async def test_weak_password_is_pinned_to_the_password_field(self):
        page, view = self._build_view()
        await self._submit(view, email="newmember@example.com",
                           password="short", confirm="short")
        self.assertFalse(view._email_error.value)
        self.assertTrue(view._password_error.value)

    async def test_mismatched_confirmation_is_pinned_to_the_confirm_field(self):
        page, view = self._build_view()
        await self._submit(view, email="newmember@example.com",
                           password=_TEST_PASSWORD, confirm="Different1!")
        self.assertFalse(view._password_error.value)
        self.assertTrue(view._confirm_password_error.value)

    async def test_successful_signup_derives_username_and_routes_to_login(self):
        page, view = self._build_view()
        await self._submit(view, email="newmember@example.com",
                           password=_TEST_PASSWORD, confirm=_TEST_PASSWORD)

        self.assertEqual(page.route, routes.LOGIN)
        self.assertTrue(self.auth.is_username_exists("newmember"))
        self.assertIsNotNone(self.auth.login_user("newmember", _TEST_PASSWORD))

    async def test_duplicate_email_is_surfaced_on_the_email_row_without_navigating(self):
        self._signup("first", "dup@example.com")
        page, view = self._build_view()

        await self._submit(view, email="dup@example.com",
                           password=_TEST_PASSWORD, confirm=_TEST_PASSWORD)

        self.assertTrue(view._email_error.value)
        self.assertEqual(page.route, SignupView.ROUTE)


# ============================================================================
#  9. MyProfileView — form validation, save round-trip, photo-upload rollback
# ============================================================================

class _FakePickedFile:
    """Stand-in for Flet's picked-file record — the two attributes
    `pick_and_upload` reads (`name`, `bytes`)."""
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self.bytes = data


class _FakeFilePicker:
    """Stand-in for `ft.FilePicker` — `pick_files` returns a canned selection
    (or `None`/`[]` to model the user dismissing the dialog)."""
    def __init__(self, files=None) -> None:
        self._files = files

    async def pick_files(self, **_kwargs):
        return self._files


class _AlwaysFailingProfileRepo:
    """Stand-in repository whose save always fails mid-transaction — drives
    `save_photo_urls_or_rollback`'s rollback path (mirrors
    `TestPhotoWriteRollbackKernel._FailingRepo`)."""
    def save_profile(self, _profile):
        raise RuntimeError("simulated save failure")


class TestMyProfileViewBehavior(_BackendMixin, unittest.IsolatedAsyncioTestCase):
    """Exercises the post-3.1-split module boundary: `MyProfileView` owns
    `_current_profile` / `_photo_urls` / `_main_image`; `my_profile_form` /
    `my_profile_photos` are stateless helpers it calls into. These tests drive
    the WHOLE lifecycle (mount → load → save / change-photo) the way the app
    does, asserting the persisted DB state — not just in-memory mutation."""

    _PNG = TestProfileStorageIntegration._PNG

    def setUp(self) -> None:
        self._build_backend()
        self.uid = self._signup("noa", "noa@example.com")

    def tearDown(self) -> None:
        self._teardown_backend()

    async def _drive(self) -> tuple[FakePage, MyProfileView]:
        page = FakePage()
        page.route = MyProfileView.ROUTE
        page.session.store.set(MyProfileView.SESSION_USER_ID_KEY, self.uid)
        view = MyProfileView(page, self.profiles, self.storage)
        page.views.append(view.build())            # mounted as the stack top
        await view._load_profile_data()
        return page, view

    def _fill_valid_form(self, view: MyProfileView) -> None:
        view._name_field.value = "נועה כהן"
        view._gender_dropdown.value = Gender.FEMALE.value
        view._dob_day.value = "15"
        view._dob_month.value = "6"
        view._dob_year.value = str(date.today().year - 40)
        view._city_field.value = "תל אביב"
        view._region_dropdown.value = "מחוז תל אביב"
        view._bio_field.value = "קצת עליי"

    # ---- load → populate -------------------------------------------------

    async def test_load_populates_form_from_the_persisted_profile(self):
        _page, view = await self._drive()
        self.assertIsNotNone(view._current_profile)
        self.assertEqual(view._current_profile.user_id, self.uid)
        # The seeded minimal profile's name mirrors the username (see
        # ProfileQueries.minimal_profile_params) — populate_form mirrors it in.
        self.assertEqual(view._name_field.value, "noa")
        self.assertEqual(view._photo_urls, [AssetPaths.DEFAULT_PROFILE_IMAGE])

    # ---- save: validation pins the first error, persists nothing ---------

    async def test_save_pins_first_validation_error_and_persists_nothing(self):
        before = self.profiles.get_profile(self.uid)
        _page, view = await self._drive()
        view._name_field.value = "   "                       # blank after strip

        await view._on_save_click(None)

        self.assertTrue(view._name_error.value)
        self.assertFalse(view._gender_error.value)           # sequential — first wins
        after = self.profiles.get_profile(self.uid)
        self.assertEqual(
            after.display_name.for_gender(after.gender),
            before.display_name.for_gender(before.gender),
        )

    async def test_incomplete_birth_date_is_pinned_without_persisting(self):
        _page, view = await self._drive()
        view._name_field.value = "נועה כהן"
        view._gender_dropdown.value = Gender.FEMALE.value
        # Day/month/year left empty.
        view._city_field.value = "תל אביב"

        await view._on_save_click(None)

        self.assertTrue(view._dob_error.value)
        reloaded = self.profiles.get_profile(self.uid)
        self.assertEqual(reloaded.date_of_birth.year, 1900)  # sentinel untouched

    # ---- save: the happy path round-trips through the real repository ----

    async def test_successful_save_persists_every_edited_field(self):
        _page, view = await self._drive()
        self._fill_valid_form(view)

        await view._on_save_click(None)

        self.assertIn("עודכן בהצלחה", view._status_text.value)
        reloaded = self.profiles.get_profile(self.uid)
        self.assertEqual(reloaded.display_name.for_gender(reloaded.gender), "נועה כהן")
        self.assertEqual(reloaded.bio.for_gender(reloaded.gender), "קצת עליי")
        self.assertEqual(reloaded.gender, Gender.FEMALE)
        self.assertEqual(reloaded.date_of_birth, date(date.today().year - 40, 6, 15))
        self.assertEqual(reloaded.location.city, "תל אביב")
        self.assertEqual(reloaded.location.region, "מחוז תל אביב")
        # UPSERT (not REPLACE) → linked credentials survive the save.
        self.assertEqual(self.auth.login_user("noa", _TEST_PASSWORD), self.uid)

    # ---- change main photo: durable swap + old-file cleanup --------------

    async def test_change_main_photo_persists_new_path_and_repaints(self):
        _page, view = await self._drive()
        old_main = view._photo_urls[0]
        self.assertEqual(old_main, AssetPaths.DEFAULT_PROFILE_IMAGE)
        view._file_picker = _FakeFilePicker([_FakePickedFile("me.png", self._PNG)])

        await view._on_change_main_photo(None)

        new_main = view._photo_urls[0]
        self.assertNotEqual(new_main, old_main)
        self.assertTrue(os.path.exists(new_main))
        self.assertEqual(
            os.path.realpath(os.path.dirname(new_main)),
            os.path.realpath(self.uploads_dir),
        )
        self.assertEqual(view._main_image.src, new_main)     # repainted
        reloaded = self.profiles.get_profile(self.uid)
        self.assertEqual(reloaded.photo_urls[0], new_main)
        self.assertIn("עודכנה בהצלחה", view._status_text.value)

    async def test_change_main_photo_cancel_leaves_everything_untouched(self):
        _page, view = await self._drive()
        before = list(view._photo_urls)
        view._file_picker = _FakeFilePicker(None)            # user dismissed the dialog

        await view._on_change_main_photo(None)

        self.assertEqual(view._photo_urls, before)
        self.assertEqual(self.profiles.get_profile(self.uid).photo_urls, tuple(before))

    async def test_change_main_photo_save_failure_rolls_back_and_reclaims_orphan(self):
        _page, view = await self._drive()
        before_urls = list(view._photo_urls)
        before_files = set(os.listdir(self.uploads_dir))
        view.profile_repo = _AlwaysFailingProfileRepo()
        view._file_picker = _FakeFilePicker([_FakePickedFile("bad.png", self._PNG)])

        await view._on_change_main_photo(None)

        # In-memory entity AND working copy rolled back to the previous list.
        self.assertEqual(view._photo_urls, before_urls)
        self.assertEqual(view._current_profile.photo_urls, tuple(before_urls))
        # The just-uploaded orphan was reclaimed — no net new file remains.
        self.assertEqual(set(os.listdir(self.uploads_dir)), before_files)
        self.assertIn("עדכון תמונת הפרופיל נכשל", view._status_text.value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
