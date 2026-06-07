# Yahdav — Engineering Contract

**Yahdav Dates App** ("יחדיו" = "together") — a Hebrew-language dating app for the
50+ community. Python + [Flet](https://flet.dev) on the UI, SQLite + local-disk
media for persistence today, Firebase pluggable as an alternate backend.

This document is **the contract**, reverse-engineered from the running code. The
rules below are **hard invariants**. If a change breaks a rule here, fix the rule
or fix the change — never quietly bypass it.

---

## Core Architectural Principles

Light **Clean Architecture** with **Interface Segregation**: outer layers depend
on inner layers, never the reverse, and each caller depends only on the slice it
actually uses.

```
┌─────────────────────────────────────────────────────────────┐
│  views/   (Flet UI) + utils/router.py                        │  ← depends on ↓
│  ────────────────────────────────────────────────────────── │
│  services/  (4 role-interfaces + concrete backends + ledger) │
│  ────────────────────────────────────────────────────────── │
│  models/   (UserProfile, value objects, enums)               │
└─────────────────────────────────────────────────────────────┘
```

### 1. Interface-driven design (the *what*, not the *how*)
No view imports a concrete service, `sqlite3`, or the filesystem. Views depend on
abstract role-interfaces; the concrete services implement them. Swapping a backend
touches only the constructor lines in `app.py`.

### 2. Interface Segregation (no god-interface)
There is **no** `IBackEndService`. Four small role-interfaces — each view depends
only on the one(s) it needs:

| Interface | Owns | Used by |
|---|---|---|
| `IAuthService` | `signup_user → bool`, `login_user → str \| None` (UID, not bool), `is_username_exists` / `is_email_exists`, **static** validators (`is_email_valid` / `is_username_valid` / `is_password_valid`), and remember-me `generate` / `validate → uid\|None` / `revoke` | `login_view`, `signup_view` |
| `IProfileRepository` | `get/save/find/delete_profile`, `discover_profiles`, `update_safety_flags`, `add_block`, `ensure_default_photo` | `profile/*`, `matching/discover`, `matching/matches_view`, router boot |
| `IMessagingService` | `send_direct_message`, `get_chat_history`, `mark_messages_as_read`, `get_unread_counts`, `get_conversations` | `matching/chat_view`, `matching/matches_view` |
| `IStorageService` | `upload_file(bytes, name) → ref`, `delete_file(ref) → bool` | `profile/my_profile_view`, `profile/additional_photos_view` |

`ChatView` cannot call `signup_user` — that method isn't on the interface it
received. Your IDE/mypy enforces what the architecture promises.

**The concrete side mirrors the split — no god object.** Each interface has its
own class, decoupled (sharing only a `db_path` / root-dir `str`, never a base class):

| Interface | Concrete class | File |
|---|---|---|
| `IAuthService` | `SqliteAuthService` | `services/sqlite_auth_service.py` |
| `IProfileRepository` | `SqliteProfileRepository` | `services/sqlite_profile_repository.py` |
| `IMessagingService` | `SqliteMessagingService` | `services/sqlite_messaging_service.py` |
| `IStorageService` | `LocalDiskStorageService` | `services/local_disk_storage_service.py` |

**The query ledger.** Every raw SQL string, DDL/index, UPSERT, pragma, and the
`connection()` / `transaction()` context managers live in ONE module,
`services/sqlite_queries.py` (`AuthQueries` / `ProfileQueries` / `MessagingQueries`).
The concrete SQLite services hold **zero inline SQL**. Value-object
serialization (Location / Lifestyle / LocalizedText / IceBreaker / photo paths /
extras → JSON, `ensure_ascii=False` so Hebrew is stored verbatim) lives in
`SqliteProfileRepository`.

### 3. Dependency Injection (DI)
The thing that uses an object doesn't build it — someone hands it in.

```python
# BAD — view builds its own backend → coupled to SQLite forever.
class LoginView:
    def __init__(self, page): self.auth = SqliteAuthService(db_path)

# GOOD — view receives only the interface it needs.
class LoginView(BaseView):
    def __init__(self, page, auth: IAuthService):
        super().__init__(page); self.auth = auth
```

The **composition root** — the one place that wires everything — is `src/app.py`.
It builds the three SQLite services (profile first, for the FKs) plus
`LocalDiskStorageService`, and registers each under its session key: `"auth"`,
`"profiles"`, `"messaging"`, `"storage"`. The router pulls the right key per view.

---

## Directory & File Structure

```
src/
├── app.py                              Composition root: build 4 services, register 4 keys, boot router.
│
├── components/                         App-wide UI primitives. NO business logic. NO backend imports.
│   ├── buttons.py                      create_primary_button / create_secondary_button
│   ├── loading.py                      show_loading / hide_loading overlay
│   └── inputs.py                       create_hebrew_text_field (RTL, oversized)
│
├── models/                             Domain entities.
│   ├── user_profile.py                 Abstract UserProfile (ABC) + value objects + enums + DI Protocols.
│   └── sqlite_user_profile.py          SQLiteUserProfile concrete dataclass (data carrier; typed setters).
│
├── services/                           Four role-interfaces + concrete backends + ledger.
│   ├── i_auth_service.py               IAuthService          (ABC)
│   ├── i_profile_repository.py         IProfileRepository    (ABC)
│   ├── i_messaging_service.py          IMessagingService     (ABC)
│   ├── i_storage_service.py            IStorageService       (ABC)
│   ├── sqlite_queries.py               Query ledger: ALL SQL + connection/transaction wrappers + pragmas.
│   ├── sqlite_auth_service.py          SqliteAuthService(IAuthService)
│   ├── sqlite_profile_repository.py    SqliteProfileRepository(IProfileRepository) — fail-soft JSON (de)serialization.
│   ├── sqlite_messaging_service.py     SqliteMessagingService(IMessagingService)
│   ├── local_disk_storage_service.py   LocalDiskStorageService(IStorageService) — media under data/uploads/.
│   └── firebase_backend.py             Monolith stub — left as-is for a future cloud backend.
│
├── utils/                              constants, validation, router, device storage, time.
│   ├── constants.py                    TextSizes, UIConstants, ThemeColors, AssetPaths, DBConfig, StorageConfig,
│   │                                   AuthConfig, FirebaseConfig, ChatConfig, MatchConfig, MessageType, MessageStatus.
│   ├── validation.py                   validate_email, validate_password.
│   ├── timeutils.py                    utcnow_naive() — the ONE UTC source (no deprecated datetime API).
│   ├── local_storage.py                Device "Remember Me" token seam (page.shared_preferences; raw token only).
│   └── router.py                       Per-route DI factories + resolve_initial_route + two-layer black-screen backstop.
│
└── views/                              Feature-organized Flet screens.
    ├── _base.py                        BaseView — stores page only; subclasses bring their own service(s).
    ├── common/                         screen (background_screen + translucent_card),
    │                                   photos (resolve_main_photo + extra_photo_urls + photo_thumb),
    │                                   navigation (back_to_menu_button), session (safe_remove),
    │                                   placeholder_view (legacy; not in the active route table).
    ├── auth/                           welcome_view, login_view, signup_view (all plain HUB BaseViews).
    ├── menu/                           main_menu_view (post-login hub; route /menu; owns logout).
    ├── onboarding/                     (future — empty package, not routed).
    ├── profile/                        my_profile_view (edit own + MAIN picture),
    │                                   additional_photos_view (portfolio extras; /profile/photos),
    │                                   user_profile_view (read-only peer; black-screen-proof).
    └── matching/                       discover_view (IProfileRepository),
                                        matches_view (IMessagingService + IProfileRepository; chat history),
                                        chat_view (IMessagingService).

tests/test_component_orchestration.py   Integration/E2E: Auth⇄Session⇄Router, Profile⇄Storage, Messaging⇄Profile.
docs/DESIGN_SYSTEM.md                    UI/UX enforcement contract (shell, typography, RTL, action colors).
```

**Two folders developers confuse:** `components/` are primitives anyone can use
(simple params in, Flet controls out — **must not** import services);
`views/<feature>/widgets/` are widgets used by only one feature.

**Configuration lives in `utils/constants.py` — never hardcoded.** DB
path/pragmas, uploads root + photo caps + allowed extensions (`StorageConfig`),
scrypt params + remember-me knobs (`AuthConfig`), theme colors, font sizes, card
opacity, asset paths, messaging enums, chat/discover page sizes, Firebase project
config — all in their respective config classes.

---

## UI Layer Rules

### Rule 1 — Every view extends `BaseView` and receives ONLY the interfaces it needs
```python
class LoginView(BaseView):
    def __init__(self, page, auth: IAuthService):
        super().__init__(page); self.auth = auth

class MyProfileView(BaseView):                       # edits profile AND its photos
    def __init__(self, page, profile_repo: IProfileRepository, storage: IStorageService):
        super().__init__(page); self.profile_repo = profile_repo; self.storage = storage
```
`BaseView.__init__` stores `self.page` and nothing else; `build()` raises
`NotImplementedError`. The router constructs the view; never call its constructor
yourself.

### Rule 2 — The backend is touched ONLY in event handlers / lifecycle tasks, ONLY via the role-interface, ONLY off-thread
```python
async def _on_login_click(self, e):
    loading.show_loading(self.page)
    try:
        uid = await asyncio.to_thread(self.auth.login_user, email, password)  # str | None
    finally:
        loading.hide_loading(self.page)
    if uid:
        self.page.session.store.set("current_user_id", uid)   # stash identity BEFORE navigating
        self.page.go("/menu")
```
**Thread-execution contract:** every blocking call — SQLite *and* disk I/O
(`storage.upload_file` / `delete_file`) — runs inside `asyncio.to_thread(...)` so
the Flet event loop and spinner keep animating. Never `time.sleep` in an async
handler — use `asyncio.sleep`. Async work kicked off on mount uses
`self.page.run_task(...)` (falling back to `asyncio.create_task` on older builds).

### Rule 3 — Hebrew / RTL is a first-class concern
- Reuse `create_hebrew_text_field`. Latin inputs (email/password) keep
  `text_align=LEFT`; Hebrew-content fields pass `hebrew_content=True` to override
  to `RIGHT`.
- Sizes from `TextSizes` (H1=50, H2=25, BUTTON=40, INPUT=25; BODY=16/SMALL=13 for
  secondary hints only) — oversized **on purpose** for the 50+ audience. Colors
  from `ThemeColors` — never a raw `"#RRGGBB"`.
- Gender-inflected strings use `LocalizedText.for_gender(viewer.gender)`.

> **⚠️ The RTL right-alignment gotcha (read before you align anything).** In this
> Flet build, `page.rtl=True` *flips* `CrossAxisAlignment.END` and
> `MainAxisAlignment.END` to the **visual left**, and a `Row` renders its **first
> child rightmost**. Aligning to `END` to mean "right" therefore produces
> left-aligned / scattered layouts. The reliable recipe:
> - **Columns:** `horizontal_alignment=CrossAxisAlignment.STRETCH` so children span full width.
> - **Text:** `text_align=TextAlign.RIGHT` (absolute, RTL-immune) on a full-width Text + `rtl=True` for shaping.
> - **Rows** (avatar / photo thumbnail on the far right): put it **first**, give the text column `expand=True`. Don't rely on `MainAxisAlignment` for left/right.
> - Setting `rtl=False` to "fix" a control does **not** take effect in this build.

### Rule 3.5 — One shared screen shell for every screen
Every screen is built from two helpers in **`views/common/screen.py`**:
`background_screen(route, content)` (full-screen `BG.png`, `BoxFit.FILL`, with a
solid `bgcolor=ThemeColors.BACKGROUND` behind it as the black-screen guard) and
`translucent_card(content, *, expand, margin, padding)` (50%-white card via
`UIConstants.FORM_OVERLAY_OPACITY`, shared corner radius). Navigation helpers live
in `views/common/navigation.py` (`back_to_menu_button`) and session helpers in
`views/common/session.py` (`safe_remove`). Photo helpers live in
`views/common/photos.py`. This shell is shared by **every** screen, including
auth (Login/Signup/Welcome are plain `ScreenType.HUB` `BaseView`s) and the
router's own error view.

### Rule 4 — Feature isolation
`views/profile/` must not import from `views/matching/`. Shared widgets →
`components/` (or `views/common/` for view-layer helpers).

### Rule 5 — The Peer Layout Boundary Rule (never blank the screen)

> **⚠️ Untrusted/partial data must never reach Flet's render tree unguarded.** A
> peer profile (or any externally-sourced record) can have null localizations,
> missing value objects, an empty photo array, or a 10k-char bio. Any of these
> throwing during `build()`/render leaves the page with no attached view — which
> the Flet desktop client renders **BLACK**. Four structural guards, applied
> wherever untrusted data is shown (canonically `user_profile_view.py`, and the
> matching feeds):
>
> 1. **Total safe accessors.** Read every field through a `_safe_*` helper that
>    NEVER raises (returns a safe default). The render builder is then a pure,
>    total function — fewer fields on bad data, never an exception. Photo `src`
>    goes through an explicit length-guarded `_safe_photo_src` that falls back to
>    the default template.
> 2. **Bounded layout.** Content lives in `background_screen(translucent_card(…))`
>    with ONE `expand=True` scroll region; Columns are `STRETCH`, Text is
>    `text_align=RIGHT`+`rtl=True` and wraps (`overflow=CLIP` on values), so a
>    long bio scrolls — it can't overflow the render tree.
> 3. **Fail-safe to a card, not a crash.** The fetch runs in `asyncio.to_thread`
>    wrapped in try/except; a fetch error, a missing profile, or a render glitch
>    swaps in a styled Hebrew error card ("משהו השתבש בטעינת הפרופיל") inside the
>    same shell. `build()` assembles only static controls (cannot throw).
> 4. **Per-item render isolation for lists.** Discover (`_candidate_tile`),
>    Matches (`_thread_row`), and Chat (`_bubble`) build each row inside its own
>    try/except, so one malformed record is skipped with a log line — it can
>    never blank or freeze the whole list. This is the render-seam analogue of
>    the fetch-seam guard, applied to a LIST of untrusted records.
>
> The **Router is the final backstop** behind all of this — see below.

---

## Routing — the Router class & the two-layer black-screen backstop

Exactly **one** place constructs views: `utils/router.py`. A `Router` maps a URL
string to a zero-arg factory that performs per-route DI.

```python
def _build_login(self) -> ft.View:
    auth = cast(IAuthService, self.page.session.store.get("auth"))
    return LoginView(self.page, auth).build()

def _build_my_profile(self) -> ft.View:                       # TWO interfaces, per ISP
    profiles = cast(IProfileRepository, self.page.session.store.get("profiles"))
    storage  = cast(IStorageService,    self.page.session.store.get("storage"))
    return MyProfileView(self.page, profiles, storage).build()
```

**Rules:** single source of view construction; per-route DI (only the
interface(s) the view needs); `typing.cast` documents the contract; any unknown
route (including `"/"` / empty) falls back to `/auth/welcome`. `/discover/profile`
and `/chat/new` read the target peer id from `selected_peer_id` (no URL path
params). Adding a route = one `_routes` entry + one `_build_<feature>` factory.

### The two-layer backstop (hard invariant — a black page must be unreachable)

`handle_route_change` wraps view construction in **two** independent guards:

- **Layer 1 — factory build.** `self._routes[route_str]()` runs in a try/except.
  A factory that raises during `build()` is logged and yields `view = None`
  (the styled error view is built later, in the guarded mount, so that building
  the error view can itself be caught).
- **Layer 2 — mount / error-view build (the backstop's backstop).** Mounting the
  view (or, if `view is None`, building `_safe_error_view()` and mounting it) runs
  in its own try/except. If anything here raises, a **completely bare,
  dependency-free** `ft.View(controls=[ft.Text(_LAST_RESORT_MSG)])` is mounted —
  no shared shell, no theme constants, no buttons — so the deepest fallback relies
  on nothing that could itself fail. A final inner try/except around even that
  bare mount logs and leaves the page on its previous view rather than crashing
  the event loop.

`_safe_error_view()` is a styled Hebrew "משהו השתבש בטעינת המסך" card in the shared
shell with a secondary "חזרה לתפריט הראשי" button. After Layer 2, a blank page is
mathematically unreachable.

A second structural guard backs this at the page level: `app.py` sets
`page.bgcolor = ThemeColors.BACKGROUND`, and `background_screen` paints a solid
`bgcolor` behind the `BG.png` image — so even a missing/slow background asset
never falls through to an unset (black) page background.

---

## Persistence invariants

1. **Absolute, stable paths — never `:memory:` or CWD-relative.** The DB lives at
   `DBConfig.DB_PATH = Path(__file__).resolve().parents[2] / "data" / "yahdav.sqlite3"`;
   media under `StorageConfig.UPLOADS_DIR = DBConfig.DB_DIR / "uploads"`. Both
   directories are `mkdir(parents=True, exist_ok=True)`'d on first use, so a fresh
   checkout creates them and **every** process resolves the same files wherever it
   was launched. Bundled assets are served from `<project_root>/assets/`, resolved
   absolutely in `app.py` via `assets_dir`. This is what makes signed-up users
   (and their photos) survive a restart.
2. **Profile writes are UPSERT, never `REPLACE`.** `SqliteProfileRepository.save_profile`
   uses `INSERT … ON CONFLICT(user_id) DO UPDATE SET …` (`ProfileQueries.UPSERT`).
   A bare `INSERT OR REPLACE` resolves a PK conflict by *deleting* the row and
   re-inserting — and with `PRAGMA foreign_keys = ON` that delete fires
   `ON DELETE CASCADE`, silently wiping the user's `auth_credentials`,
   `user_sessions`, and `direct_messages`. UPSERT mutates in place (same rowid, no
   delete, no cascade), so a profile edit — including adding/removing a **photo
   path** — can never destroy credentials or remembered sessions.
   `ON CONFLICT(user_id)` targets only the PK, so a real UNIQUE collision on
   `email`/`phone` (a *different* user) still raises `IntegrityError`, surfaced as
   `ValueError`.
3. **Multi-statement writes are atomic.** Connections run in autocommit
   (`ISOLATION_LEVEL = None`), so multi-row writes use the ledger's
   `transaction(db_path)` wrapper (`BEGIN` / `COMMIT` / `ROLLBACK`). `signup_user`
   wraps its minimal-profile + credentials inserts in one transaction — no orphaned
   `user_profiles` row.
4. **Isolated thread execution.** `connection()` opens a **fresh** connection per
   call, applies all pragmas, and **always** closes it in `finally`, so no handle
   crosses a thread boundary — that's what makes the services safe under
   `asyncio.to_thread`. `LocalDiskStorageService` follows the same contract: each
   `upload_file`/`delete_file` opens and closes its own file handle, sharing no
   mutable state across threads.
5. **Photo write/delete ordering (no dangling references).** Adding/overwriting a
   photo writes the new file FIRST, then UPSERTs the path list; a save failure
   rolls back the in-memory entity **and** deletes the orphan file. Removing /
   overwriting deletes the old file only AFTER the UPSERT succeeds (and never the
   bundled default template — `delete_file` refuses it anyway, as it sits outside
   the storage root). So a crash can at worst leave an orphan file, never a DB row
   pointing at a missing image. Changing the MAIN picture overwrites index 0 and
   deletes the previous main file.
6. **One UTC source, no deprecated API.** Every timestamp is written via
   `utils/timeutils.utcnow_naive()`. Password hashing reads cost params from
   `AuthConfig.SCRYPT_*`. *Known gaps (flagged for follow-up):* the
   `scrypt$salt$hash` format doesn't version its cost params, and although
   `AuthConfig` defines lockout thresholds, login lockout is not yet enforced.

### Fail-soft deserialization (the JSON read path is total)

`SqliteProfileRepository._hydrate` parses every nested column through helpers that
**never raise** — the heart of the black-screen elimination on the data side:

- `_col(row, key, default)` tolerates a column missing under schema drift.
- `_loads(raw, default)` returns `default` on any malformed/empty/non-str JSON.
- `_lt_from_json` / `_location_from_json` / `_lifestyle_from_json` /
  `_ice_breakers_from_json` / `_extras_from_json` read **only known fields** and
  drop unexpected/renamed keys, so a schema-drifted row can't blow up a
  constructor; `_gender_from` / `_status_from` / `_flags_from` fall back to safe
  enum defaults; `_date_from_iso` falls back to the `1900-01-01` un-onboarded
  sentinel (views skip it).
- `_photos_from_json` → tuple of non-empty strings; `_with_default_main` then
  guarantees the in-memory list is **never empty** (index 0 resolves to the
  default template), so no downstream access — index 0 or the `1..4` slice — can
  fail or render an empty `src`.

All read methods (`get_profile`, `find_profile_by_email`, `discover_profiles`)
wrap the whole operation in try/except and return `None` / `[]` on error — the
read path is fail-soft and never crashes a view.

---

## Session-store key conventions

`page.session.store` is the only mutable global the views see. Keep its key space
small and documented:

| Key | Written by | Read by | Lifetime |
|---|---|---|---|
| `"auth"` / `"profiles"` / `"messaging"` / `"storage"` | `app.py` (composition root) | router factories | process |
| `"current_user_id"` | `login_view` **or** `Router.resolve_initial_route` (auto-login) | every user-scoped view + router boot | until logout / exit |
| `"current_user_email"` | same as above | recovery / display flows | until logout / exit |
| `"selected_peer_id"` | `DiscoverView` (action sheet) / `MatchesView` (open thread) | `ChatView`, `UserProfileView` (injected by the router) | until next selection |

- `IAuthService.login_user(...) → str | None` returns the UID (not a bool) so the
  view stashes it into `"current_user_id"` **before** `page.go(...)` — no second
  round-trip.
- **User-scoped views defensively check the token:** a missing/orphaned
  `current_user_id` → Hebrew "אנא התחבר/י תחילה" banner, then a bounce to
  `/auth/login`. `ChatView` additionally re-validates that the injected `self_id`
  matches the session's `current_user_id`.
- The remember-me device token is **not** a session key — it lives on the device
  via `utils/local_storage.py` (`page.shared_preferences`). Never widen the key
  set without updating this table.
- **Use `safe_remove` for cleanup.** `views/common/session.py::safe_remove` wraps
  `SessionStore.remove` with a `contains_key` check (a bare `.remove` raises
  `KeyError` on a missing key). Defensive cleanup paths (logout, login pre-flight)
  MUST use it.

---

## Media / Storage Subsystem

Photos are a first-class subsystem behind `IStorageService`, isolated from
`IProfileRepository` (the profile repo is **not** bloated with file I/O).

- **Interface** (`i_storage_service.py`): `upload_file(file_bytes, destination_filename) → str`
  returns a stable reference (a local absolute path today, a URI on a future
  backend); `delete_file(file_path) → bool` is fail-soft. Both are **blocking** —
  callers MUST wrap them in `asyncio.to_thread`.
- **Concrete** (`local_disk_storage_service.py`): writes under an absolute root
  (`StorageConfig.UPLOADS_DIR`), `mkdir`'d on construction. `_safe_name` derives a
  **path-safe, collision-free** name from the caller hint — strips any directory
  component (traversal guard), keeps only an allowed image extension (else a safe
  `.img` fallback), and prefixes a fresh UUID. `delete_file` refuses to unlink
  anything whose resolved path is not inside the root, never raises, and treats an
  already-absent file as "not deleted".
- **Photo-list convention** — `UserProfile.photo_urls: tuple[str, …]` (with a
  normalizing setter that keeps only non-empty strings) is one ordered list:
  **index 0 = the single MAIN profile picture**, **index 1.. = ADDITIONAL photos**
  (capped by `MAX_EXTRA_PHOTOS`). The repository serializes it to `photo_urls_json`.
- **Default main picture — never null.** Registration seeds
  `photo_urls = [AssetPaths.DEFAULT_PROFILE_IMAGE]` via
  `ProfileQueries.minimal_profile_params` (single source:
  `ProfileQueries.DEFAULT_PHOTOS_JSON`). Three layers keep old rows (null / empty /
  `'[]'` / `'null'` / missing column) from crashing:
  1. *Fetch-layer resolution* — `_photos_from_json` → `_with_default_main`, so a
     fetched profile's `photo_urls` is **never empty**.
  2. *Safe accessors* — `views/common/photos.py::resolve_main_photo` (length-checked
     index 0 → default) and `extra_photo_urls` (slice → `[]`, empties dropped) are
     the read paths; no view indexes the raw list. The read-only peer view adds its
     own `_safe_photo_src` length guard.
  3. *Lazy migration — decoupled from the read path.*
     `IProfileRepository.ensure_default_photo(user_id)` is a conditional,
     idempotent, best-effort `UPDATE` (`ProfileQueries.HEAL_MISSING_PHOTOS` heals
     only `NULL`/`''`/`'[]'`/`'null'` rows, never raises, single-column so it
     can't cascade). It is **never chained into a fetch**: `MyProfileView`'s
     profile load is a pure, write-free read, and the heal is dispatched
     separately as a **fire-and-forget background task** (`_schedule_photo_heal`
     → `page.run_task`, `asyncio.to_thread`) *after* the load resolves. So the
     critical read never triggers a WAL `UPDATE` or contends for a write lock —
     display is already correct via layers 1–2, and this is pure persistence
     catch-up that permanently fixes an old account without blocking the view.
- **Views** — `my_profile_view.py` shows the MAIN picture at the top (tap to
  overwrite, camera badge) with a "תמונות נוספות" button beneath it that navigates
  to `AdditionalPhotosView` (`/profile/photos`), which manages the extras
  (`photo_urls[1:]`) — kept separate from the main picture. Both build inside the
  shared `translucent_card`, follow the RTL recipe, and reuse `photo_thumb`. A
  `ft.FilePicker` is a Flet **service**, attached to **the built view's** `services`
  list (`view.services.append(picker)`) — NOT `page.services`, which still points
  at the outgoing view during `build()`. Bytes come from
  `pick_files(with_data=True)` (awaitable in 0.84 — no `on_result` callback),
  stored off-thread, and the updated path list is saved via `save_profile`. See
  persistence invariant **#5**.

`StorageConfig` (`utils/constants.py`): `UPLOADS_DIR`, `MAX_PROFILE_PHOTOS` (5),
`MAX_EXTRA_PHOTOS` (4), `ALLOWED_IMAGE_EXTS`.

---

## Direct Messaging Subsystem

A first-class subsystem inside `IMessagingService`; the chat UI is identical on
SQLite (today) or a real-time provider (later).

**Domain types** (`utils/constants.py`): `MessageType {TEXT=1, AUDIO=2, IMAGE=3}`,
`MessageStatus {SENT=1, DELIVERED=2, READ=3}` — integer values are the on-disk
contract; **append, never renumber**. `ChatConfig` holds page sizes, payload caps,
and storage prefixes.

**Interface** (the only chat API the UI sees):

| Method | Purpose |
|---|---|
| `send_direct_message(sender, recipient, content, msg_type) → uuid` | Persist a message. For `AUDIO`/`IMAGE`, `content` is a storage reference. |
| `get_chat_history(a, b, limit, cursor_timestamp=None) → list[dict]` | **Cursor**-paginated, **chronological** (oldest→newest). `None` ⇒ newest page. |
| `mark_messages_as_read(owner, sender) → None` | Monotonic `SENT`/`DELIVERED` → `READ`. |
| `get_unread_counts(user) → dict[sender_id, int]` | Drives the unread badge. |
| `get_conversations(user) → list[dict]` | Threads newest-first: `{peer_id, last_content, last_msg_type, last_sender_id, last_at}`. |

Returned dicts are JSON-shaped (`msg_type`/`status` as enum `.name`); read paths
never import the enums.

**`conversation_id`** = `"|".join(sorted([a, b]))` (`ChatConfig.CONVERSATION_SEPARATOR`)
— both directions share one deterministic key, collapsing history paging to a
single indexed lookup (no `OR`/`UNION`/post-sort).

**Compound indexes** on `direct_messages`, one per query:
`idx_dm_conv_time (conversation_id, created_at DESC)` for history;
`idx_dm_unread (recipient_id, status, sender_id)` for unread counts;
`idx_dm_endpoints (sender_id, recipient_id, created_at)` for directional scans.
A `CHECK (sender_id <> recipient_id)` constraint forbids self-messages.

**Pagination (cursor-based, not offset).** `limit` is clamped to
`[1, MAX_PAGE_SIZE]`; paging is driven by a `cursor_timestamp` — the `created_at`
of the oldest message already on screen — **never** a SQL `OFFSET`. This keeps the
contract portable to a NoSQL backend (Firestore `startAfter`), where `offset` is
expensive and grows linearly with the page index. Two ledger queries back it:
`SELECT_HISTORY_LATEST` (no cursor ⇒ newest page) and `SELECT_HISTORY_BEFORE`
(`created_at < ?` ⇒ the page strictly older than the cursor). Both fetch
newest-first on `idx_dm_conv_time` (so paging stays `O(limit)`), then the service
`reversed()`s the slice so the UI renders top-down without re-sorting. A `None`
cursor is the most recent page; `ChatView` loads it on mount and after each send.

**Chat bubble alignment (hard rule — RTL-immune).** `ChatView._bubble` sets a
bubble's side with **absolute** container alignment: the wrapper `Container` fills
the list width and `ft.Alignment(1, 0)` pins *my* messages to the right while
`ft.Alignment(-1, 0)` pins the *peer's* to the left. Absolute coordinates are
unaffected by the RTL main-axis flip that bites `CrossAxisAlignment`-based
layouts. Do **not** rewrite this to use `END`/`START` alignment. Defensive dict
access: a missing `sender_id` degrades to a peer bubble; a missing/NULL/non-str
`content` degrades to `""` (an `ft.Text(None)` would be a render-time risk).

**Voice notes** (`MessageType.AUDIO`) are a planned **primary** channel for the
50+ audience (typing Hebrew is slow); `ChatConfig.MAX_AUDIO_DURATION_SEC` (120s)
is a UX cap. The composer currently sends `TEXT`.

---

## "Remember Me" — token-based auto-login

The "הישאר מחובר" checkbox lands a senior on their menu without retyping
credentials. **Token-based, never credential-caching:** the device sees only an
opaque, server-minted, expiring token.

| | Stored | Holds |
|---|---|---|
| **Device** (`page.shared_preferences` via `utils/local_storage.py`) | ONLY the **raw** token | nothing else |
| **Server** (`user_sessions` table) | the token's **SHA-256 hash** + `user_id` + `created_at` + `expires_at` | never the raw token |

A DB leak yields only hashes; a stolen device yields a token that expires and can
be revoked (`ON DELETE CASCADE` from the profile revokes every device). The DB is
authoritative: on boot the token is hashed, looked up, and resolved to its owner's
uid. **There is no JSON file and no `page.client_storage`** — device storage is
exclusively `page.shared_preferences` (async `get`/`set`/`remove`).

**Three `IAuthService` methods:** `generate_remember_me_token(uid) → str` (mints
`secrets.token_urlsafe(REMEMBER_ME_TOKEN_BYTES)`, stores the hash with a
`REMEMBER_ME_DAYS` expiry, returns the raw token); `validate_remember_me_token(token) → str | None`
(hashes, looks up, returns uid if unexpired else `None`, self-purging the dead
row); `revoke_remember_me_token(token) → None` (idempotent server-side delete for
explicit logout). Strength/lifetime/key all in `AuthConfig`.

**Boot interception** — `Router.resolve_initial_route()` runs from the composition
root *after* `page.update()` flushes the first frame:
1. **Event-driven settle (no fixed delay).** `_mount_boot_spinner()` paints a calm
   full-screen spinner in the shared shell (a real view, since `page.views` is
   empty at boot — black-screen-proof), then `read_token` **awaits** the
   `shared_preferences` read directly. That `await` *is* the settle: the client
   round-trip resolves exactly when the bridge answers (token or `None`) — no
   race, no wasted hardcoded sleep. (This replaced the old `_BOOT_SETTLE_SEC`.)
2. If a token is present, **one** `asyncio.to_thread` runs
   `validate_remember_me_token` + `get_profile` (orphan check).
3. Success stashes `current_user_id` + `current_user_email` and
   `page.go("/menu")`; the navigation replaces the boot spinner in place.
4. Any failure (no token / expired / orphaned account / error) clears the device
   token and falls back to `_fallback_route()` — which **preserves a valid
   deep-link** in `page.route` if there is one, else `/auth/welcome`.

**Login** mints + `write_token` when the box is ticked, or proactively
`clear_token`s when it isn't. **Logout** (`main_menu_view._on_logout_click`,
`async`) is a hard reset in order: `clear_token` (device) → `safe_remove` identity
keys (RAM) → `page.views.clear()` (kill back-button history) → `page.go("/auth/welcome")`.
Service singletons (`auth`/`profiles`/`messaging`/`storage`) **survive** logout —
they're process state, not per-user state.

---

## Session lifecycle: login & logout

The login → use → logout → re-login cycle must be **isolated** — a messy logout
corrupts the next user's session.

**Login pre-flight** (before any validation or backend call):
`safe_remove(page, "current_user_id", "current_user_email")` clears any stale UID
from a crashed/aborted prior flow. Without it, a failed login could leave the old
user's UID in the store and a subsequent navigation would load the wrong profile.

**Logout** is the hard reset described under Remember Me above. Server-side token
revocation is intentionally **not** performed on logout (per the original design):
the device token is cleared, so auto-login is broken regardless, and the orphaned
DB row simply expires (`revoke_remember_me_token` exists on the interface for
flows that do want server-side invalidation).

---

## Discover Feed

`views/matching/discover_view.py` (route `/matching/discover`) browses other
members. Proof that *feature folder ≠ interface*: it lives under `matching/` but
depends on **`IProfileRepository`** (`discover_profiles(viewer_id, limit)`), never
messaging. The contract: exclude the viewer / blocked / ineligible
(`status NOT IN (PENDING, ACTIVE)` are excluded by the SQL — only PENDING and
ACTIVE are shown); newest-registered first, capped at `limit`; returns `[]` (never
raises) on error so the feed degrades to an empty-state banner; `limit` clamped to
`MatchConfig.MAX_DISCOVER_PAGE_SIZE`, called with `DISCOVER_PAGE_SIZE` (30). The
SQLite path does it in one round-trip (correlated subquery on the `user_blocks`
PK, no N+1). Defensive identity check + shared shell + RTL row recipe (avatar far
right) + presence dot (`ThemeColors.ONLINE`/`OFFLINE`) + 86px tap targets opening
an RTL selection sheet (view profile / start chat, both stashing
`selected_peer_id`). Each tile is built in an isolated try/except (Rule 5.4).

---

## Local Data & Secrets — what stays off GitHub

`.gitignore` is the enforcement layer:

| Category | Why gitignored |
|---|---|
| SQLite files (`*.sqlite3`, `*.db-wal`, …, `data/`) | Local dev DB holds hashed passwords, profiles, chat history; binary diffs cause merge conflicts. |
| Local media (`uploads/`, `data/uploads/`, `media/`, …) | Profile photos are user data; `photo_urls` paths point here. |
| Secrets (`.env`, `serviceAccountKey.json`, `*.pem`, `*.key`) | A leaked Firebase key = full write access. If committed, **rotate in the provider console — `git rm` is not mitigation**. |
| Virtual envs + caches (`.venv/`, `__pycache__/`, …) | Trivially regenerated; bloats clones. |

The bundled `assets/` dir (`BG.png`, `UNDEFINED_PROFILE.png`) IS tracked — it's
shipped, not user data. Adding a `.gitignore` rule doesn't untrack already-tracked
files — use `git rm --cached <path>`.

---

## Testing — integration over mocks

`tests/test_component_orchestration.py` (stdlib `unittest`, run
`python -m unittest discover -s tests`) verifies component **boundaries** with the
real services against a dedicated temp SQLite path + uploads dir — nothing mocked.
Suites: **Auth⇄Session⇄Router** (login returns a UID; remember-me stores a SHA-256
*hash*, never the raw token; cold boot awaits the device-token read, resolves
identity and routes to `/menu`, else `/auth/welcome` + token purge — driven by a
minimal `FakePage` that records navigation); **Profile⇄Storage** (bytes → `data/uploads/`
off-thread → path saved via `save_profile`; the UPSERT updates in place and does
NOT cascade-delete credentials/sessions); **Messaging⇄Profile** (the messaging
service is block-agnostic; the block gate is enforced in the profile layer). Add
new integration coverage here as boundaries grow.

---

## Anti-patterns — please don't

- ❌ `import sqlite3` (or filesystem writes) anywhere outside `services/`.
- ❌ Building a concrete service (`SqliteAuthService()`, `LocalDiskStorageService()`, …) inside a view.
- ❌ Inline SQL in a concrete service — every statement goes in `sqlite_queries.py`.
- ❌ `INSERT OR REPLACE` on `user_profiles` (it cascades). Use the `UPSERT`.
- ❌ Type-hinting a view's backend as `object`/`Any` to dodge picking an interface — the god-interface in a different shirt.
- ❌ Folding file I/O into `IProfileRepository` — media belongs on `IStorageService`.
- ❌ Hardcoded paths, magic numbers, raw color/hex strings — put them in `utils/constants.py`.
- ❌ Raw `ft.TextField(...)` in a view (use `create_hebrew_text_field`), a custom `bgcolor` view shell (use `background_screen`), or `CrossAxisAlignment.END` / `MainAxisAlignment.END` to mean "right" (the RTL trap).
- ❌ Chat-bubble sides via `END`/`START` — use absolute `ft.Alignment(±1, 0)`.
- ❌ `time.sleep` in async handlers; blocking SQLite/disk calls not wrapped in `asyncio.to_thread`.
- ❌ Letting a `build()` index untrusted data, or skipping a `_safe_*` accessor for peer/feed data (the black-screen risk).
- ❌ Attaching a `FilePicker` to `page.services` (attach to the built view's `services`).
- ❌ Cross-feature view imports (`views/profile/` importing from `views/matching/`).
- ❌ Adding a public method to a concrete backend that isn't on its role-interface.
- ❌ Committing the dev SQLite file, uploaded media, or any `.env` / `serviceAccountKey.json`.

If you're unsure: read this file, then ask. The rules keep us swappable — and the
screen never goes black.
