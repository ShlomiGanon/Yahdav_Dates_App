# Repo Organization — Findings & Recommendations

A short, descriptive/advisory report on the structure of the `views`/`services`
layers, written while working through the frame-unification refactor (every
screen now renders through one `BaseView` card path — see
[`DESIGN_SYSTEM.md` §1.5](DESIGN_SYSTEM.md)). **This document recommends; it does
not change code.** Any structural moves below are a separate, opt-in follow-up.

---

## 1. `views/common/` is an 11-file junk drawer

`views/common/` currently holds 10 modules (1,212 lines) plus `__init__.py`,
mixing four genuinely different concerns under one folder name:

| Concern | Files | Lines |
|---|---|---|
| **Rendering engine** — the structural primitives & `UIComponent → ft.Control` compiler that `BaseView` is built on | `screen.py`, `renderer.py` | 243 + 486 = 729 |
| **Cross-cutting view utilities** — stateless helpers any screen may import | `navigation.py`, `session.py`, `load_flow.py`, `photos.py`, `photo_ops.py`, `render.py` | 68+18+107+63+69+55 = 380 |
| **Actual shared *views*** — things the router mounts directly | `system_views.py`, `placeholder_view.py` | 58 + 45 = 103 |

These three groups have different audiences and different churn rates: the
engine changes when the *frame* changes (rare, structural — exactly what this
refactor touched); the utilities change when a *feature* needs a new helper
(frequent, additive); the shared views change like any other screen. Today,
"go look in `views/common`" could mean any of the three, and a newcomer has no
way to tell which files are load-bearing infrastructure versus which are
ordinary, swappable helpers.

**Recommendation**: split along those lines, e.g.

```
views/common/
├── engine/            # screen.py, renderer.py — the structural compiler
├── (helpers stay or move to views/_shared utils — navigation.py, session.py,
│    load_flow.py, photos.py, photo_ops.py, render.py)
└── views/             # system_views.py, placeholder_view.py — actual screens
```

The exact grouping matters less than separating "the engine `BaseView` is built
from" (changes with the frame) from "helpers screens borrow" (changes with
features) from "views the router mounts" (changes like any other screen).

---

## 2. Naming collision: `render.py` vs `renderer.py`

`views/common/render.py` (55 lines — `build_items_safe`, the defensive
list-rendering helper for the Peer Layout Boundary Rule) and
`views/common/renderer.py` (486 lines — `ViewRenderer`/`UIComponent`/`ui.raw`,
the declarative-schema → Flet engine) are two unrelated modules whose names
differ by three letters.

This isn't a hypothetical risk — it's already a daily reality for four screens.
`chat_view.py`, `discover_view.py`, `matches_view.py`, and `peer_photos_view.py`
each import **both**, two lines apart:

```python
from views.common import renderer as ui          # the UI-schema engine
...
from views.common.render import build_items_safe  # the safe-list-builder
```

Any IDE auto-import, fuzzy search, or quick `Ctrl+click` is one keystroke away
from landing in the wrong file — and `git grep render` returns both modules
interleaved.

**Recommendation**: rename one. `render.py` is the smaller, narrower-purpose
module (one function, one job — "safely build a list of items from untrusted
records") — a name like `safe_list.py` or `list_render.py` would describe its
actual job and free `render`/`renderer` from being near-synonyms. Renaming the
486-line engine module instead would touch 15 import sites vs. 4.

---

## 3. `services/` flatly mixes interfaces and implementations

All 10 files in `services/` sit at the same level:

```
i_auth_service.py            i_messaging_service.py
i_profile_repository.py      i_storage_service.py
sqlite_auth_service.py       sqlite_messaging_service.py
sqlite_profile_repository.py sqlite_queries.py
firebase_backend.py          local_disk_storage_service.py
```

The `i_*` files are the four role-interfaces (`IAuthService`,
`IMessagingService`, `IProfileRepository`, `IStorageService`) the rest of the
app depends on — the Interface-Segregation story `ENGINEERING_CONTRACT.md`
documents and `app.py`'s composition root wires up. The other six are concrete
backends: a SQLite trio (+ its shared SQL ledger `sqlite_queries.py`), a
`firebase_backend.py` stub for a future cloud backend, and
`local_disk_storage_service.py` for photo storage. Interleaved alphabetically,
the architectural story — "depend on the four interfaces; swap the concretes
freely" — is invisible from a directory listing; you have to read filenames
closely (or already know the convention) to separate contract from
implementation.

**Recommendation**: group by role, e.g.

```
services/
├── interfaces/   # i_auth_service.py, i_messaging_service.py, …
├── sqlite/       # sqlite_auth_service.py, sqlite_messaging_service.py,
│                 # sqlite_profile_repository.py, sqlite_queries.py
├── firebase/     # firebase_backend.py
└── local/        # local_disk_storage_service.py
```

This makes "what can I depend on" (`interfaces/`) and "what concretely backs
it today" (everything else) visually obvious at a glance — and gives the
inevitable next backend (the Firebase stub is explicitly left "for a future
cloud backend") an obvious home instead of another flat file at the root.

---

## 4. Other observations surfaced along the way

- **`get_view_schema()` is now dead transitional scaffolding.** `BaseView`
  still carries a documented "legacy seam" — `get_view_schema()` returns `None`
  by default, and `_resolve_regions` branches on it to support
  not-yet-migrated screens that hand back a whole `ViewContent` (see
  `views/_base.py` lines 112–117, 145–148). A repo-wide search turns up **zero
  overrides** — every screen has migrated to `get_header`/`get_content`/
  `get_actions`. The seam (and its branch in `_resolve_regions`) is now a
  candidate for deletion in a future cleanup; it's pure migration scaffolding
  with no live callers.

- **Doc/comment fallout from the frame-unification refactor.** While preparing
  this report I found and fixed three small, now-stale artifacts the refactor
  left behind (mechanical doc/comment fixes, not structural — already applied):
  - `docs/ENGINEERING_CONTRACT.md` still named auth screens "plain
    `ScreenType.HUB` `BaseView`s" — the enum no longer exists.
  - `chat_view.py`'s module docstring still described "a sticky bottom action
    bar" — the unified frame renders actions inline at the card's tail, not in
    a separate bar.
  - `dividers.py`'s `create_action_divider` docstrings still said "for the
    sticky action bar" — it now separates inline actions at the card tail.

  These were the last loose threads; a final repo-wide grep for
  `ScreenType|SCREEN_TYPE|BodyLayout.*HUB|action_bar|sticky.*action|hub_screen|
  content_screen|_compose_frame|_hub_root|_content_root` now returns matches
  only in the two *historical* refactor write-ups under `reports/`
  (`VIEW_REFACTOR_REPORT.md`, describing the *previous* HUB/CONTENT split as a
  point-in-time snapshot — correctly left alone, the way a changelog entry
  should be) and in `views/_base.py`'s own "absorbed from…" note (which
  correctly *names* the old symbols it replaced, as history).

- **`docs/` vs `reports/` — two places write-ups land.** `docs/` holds the two
  living reference documents (`DESIGN_SYSTEM.md`, `ENGINEERING_CONTRACT.md`)
  that describe the *current* contract and are expected to be kept in sync with
  the code (as this refactor's doc pass did). `reports/` holds three
  point-in-time write-ups (`REFACTORING_REPORT.md`, `VIEW_REFACTOR_REPORT.md`,
  `CODE_QUALITY_FOLLOWUP_REPORT.txt`) that intentionally describe a past state
  and are *not* meant to track the present. The distinction is sound and worth
  keeping explicit (e.g. a one-line note at the top of each new report saying
  which kind it is) — it's what lets `VIEW_REFACTOR_REPORT.md`'s now-superseded
  description of the HUB/CONTENT split sit there validly, as history, rather
  than as drift.
