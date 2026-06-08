# Yahdav UI/UX Design System — Enforcement Contract

Audience: **50+**. Every screen must feel identical — oversized, calm, RTL-native,
and predictable. This document is the enforcement contract, reverse-engineered
from the running UI code. Deviations are bugs, not "style choices". The rules
below are backed by shared primitives so that *using the primitive* is the same
thing as *complying*.

---

## 1. The Shared Card Shell Contract

**Every** screen — auth, menu, profile, photos, discover, chat, matches, the
read-only peer profile, *the router's own cold-boot spinner*, *and the router's
own error view* — embeds its content in the two shared helpers from
`views/common/screen.py`, and nothing else:

```python
card = translucent_card(<content>, expand=…, margin=…, padding=…)   # 50%-white overlay
view = background_screen(self.ROUTE, <layout-containing-card>)       # full-bleed BG.png (BoxFit.FILL)
```

- **No view paints its own background.** `background_screen` owns the `BG.png`
  fill (`BoxFit.FILL`, STRETCH width, expand height) **and** the black-screen
  guard: a solid `bgcolor=DS.palette.background` sits *behind* the image, so a
  missing/slow asset never falls through to an unset (black) page background.
  `app.py` also sets `page.bgcolor = DS.palette.background` as a belt to that
  suspenders.
- **No view invents structural margins/padding.** Use `translucent_card`'s
  params. The opacity is `DS.opacity.form_overlay` (0.5), the radius is
  `DS.radius.card`, the default padding is `DS.pad.card`.
  One definition, tuned in one place.
- **Photo tiles** reuse `views/common/helpers/photos.py::photo_thumb(src, size=…)` — the
  single rounded/clipped image tile with a broken-image `error_content` fallback.
- **Auth screens use the same shell.** Login, Signup and Welcome are ordinary
  `BaseView`s (§1.5) — there is NO bespoke auth modal/scrim. They provide
  `get_header`/`get_content`/`get_actions` like every other screen, so they
  render the identical centered card everyone else does.

**Enforcement:** a view that constructs a raw `ft.View` with its own `bgcolor`, or
hardcodes `padding=…` on a top-level container, fails review.

---

## 1.5 The Interface-First screen framework

Every screen is an **Interface-First** `BaseView`: it DECLARES what it is and
PROVIDES its pieces through fixed methods — it never writes `build()` and never
touches layout. The engine (`BaseView.build()` in `views/_base.py`, composing the
shared primitives in `views/common/screen.py`) orchestrates everything:
assembly, centering, responsiveness, lifecycle binding, and a built-in error
catch-all.

**Every screen renders inside the SAME single card** — Welcome/Login's shape:
one centred, translucent, width-clamped card holding header → content → status
banner → actions, stacked in one DS-spaced column. There is no second frame, no
HUB/CONTENT split, and no separate action bar to keep in sync — "looks like
Welcome" is not a convention to remember, it is the only thing the engine knows
how to draw.

A screen DECLARES (class attributes):

- `ROUTE` — its route string.
- `EXPAND_BODY` — `False` (the default — Welcome/Login/Signup/Menu/Settings/
  Placeholder/UserProfile/Discover): the card sizes to its content and sits
  centred on the screen, like a dialog. `True` (Chat/Matches/MyProfile/the photo
  screens — anything with a long, internally-scrolling body): the SAME card
  instead grows to fill the viewport and scrolls its own content, like a tall
  dialog. Either way it is the identical card — chrome, width-clamp, centring,
  corner radius, translucency, header→content→actions order — just sized
  differently.
- `BODY_LAYOUT` — `BodyLayout.SCROLLING` (default; the engine wraps the body in
  its own AUTO-scroll region) or `SELF_SCROLLING` when the body already owns its
  scroll (an `ft.ListView`/`ft.Column(expand=True, scroll=...)`), so the engine
  places it directly and scrolling never nests.

A screen PROVIDES (override what it needs — each returns `ui.UIComponent`(s),
the declarative schema rendered by `views/common/renderer.py`; see §1.5.1):

- `get_header() -> ui.UIComponent | None` — the screen's H1. Rendered as the
  body's first slot and RE-STAMPED centred by the engine — a screen never picks
  its own heading alignment. Default `None`.
- `get_content() -> list[ui.UIComponent]` — REQUIRED in spirit (default `[]`).
  The body's remaining content nodes, stacked with one DS spacing.
- `get_actions() -> list[ui.UIComponent]` — buttons, rendered inline at the
  card's tail (after the body and any status banner) — exactly like
  `WelcomeView.get_actions()`. Default `[]`.
- `get_status_banner() -> ui.UIComponent | None` — an inline banner stacked
  between the content and the actions — never inside the scroll region. Default
  `None`.
- `get_overlay() -> ui.UIComponent | None` — a fullscreen layer (e.g. a
  lightbox), stacked OVER the whole card frame by the engine. Default `None`.
- `get_services() -> list[ft.Control]` — Flet services (e.g. an `ft.FilePicker`)
  mounted alongside the view. Default `[]`.

```python
class ChatView(BaseView):
    ROUTE = "/matching/chat"
    EXPAND_BODY = True                         # long message history → fill the viewport
    BODY_LAYOUT = BodyLayout.SELF_SCROLLING     # the message ListView owns its scroll

    def get_header(self) -> ui.UIComponent: return ui.raw(self._heading)         # dynamic peer name
    def get_content(self) -> list[ui.UIComponent]: return [ui.raw(self._messages)]
    def get_actions(self):       return [ui.raw(self._send_row), ui.raw(back_button(self.page, ...))]
    def get_status_banner(self): return ui.raw(self._status_banner)
    def get_services(self):      return [self._file_picker]
```

The hard SoC line is **engine = card frame; view = what fills its slots** — the
view never arranges its own chrome, the engine never reaches into the view's
content. Every provider is rendered through `guard`, so a failure in any one of
them degrades to the shared Error Component (§1.6) instead of crashing the
screen.

```
┌────────────────────────────────────────┐
│   responsive_card (centred, clamped)    │
│  ┌───────────────────────────────────┐  │
│  │  header                            │  │  ← the body's first slot,
│  │  content … (scrolls if EXPAND_BODY)│  │     always centred
│  │  [status banner]                   │  │  ← inline, between content & actions
│  │  [action] [action] …               │  │  ← inline, at the card's tail
│  └───────────────────────────────────┘  │
└────────────────────────────────────────┘
```

Hard rules, all encoded in the engine:

- **One card, one stacking order, for every screen.** Header → content → status
  banner → actions, top to bottom, inside the SAME translucent card — never a
  separate region, bar, or hand-rolled assembly. A screen that needs its back
  button to "stay on screen while the form scrolls" gets that for free: when
  `EXPAND_BODY = True`, only the *content* scrolls (or self-scrolls); the
  header, banner and actions stay pinned at the card's edges.
- **`EXPAND_BODY` is a sizing knob, not a different look.** `False` → the card
  hugs its content and centres like a dialog (Welcome's shape — the default).
  `True` → the identical card grows to fill the viewport and scrolls its own
  content internally (a "tall dialog" — chat/matches/photos/long forms). Same
  chrome, same width-clamp, same spacing/colors/corner-radius either way.
- **One heading rule.** Every screen's `get_header()` renders centred — the DS
  rule (`DS.body.heading_align`), re-stamped by the engine regardless of what
  the screen returns. A screen never overrides heading alignment.
- **Status banners sit inline, at the card's tail — never inside the scroll
  region.** Returned via `get_status_banner()`, the engine places them between
  the content and the actions, so save/error/empty-state feedback is always
  visible without competing with the scrolling body for space.
- **Primary (red) vs secondary/navigation (blue-grey) are separated by a
  divider** (see §4). The geometry — card padding, spacing, width-clamp,
  corner-radius, translucency — is defined ONCE in the Design System
  (`DS.pad.*`, `DS.spacing.*`, `DS.sizing.*`) and read directly by `BaseView`;
  views never re-invent it.
- **Canonical top-logo clearance.** An `EXPAND_BODY` card — the only shape whose
  top edge can reach the viewport's top edge — gets one taller padding
  (`DS.pad.content_card_tall` / `CONTENT_CARD_PADDING_TALL`) so its heading
  clears the BG's top logo uniformly app-wide; no view passes its own padding.
- **Overlays belong to the engine.** A fullscreen layer (e.g. the peer album's
  lightbox) is returned from `get_overlay()`; `BaseView` owns the `ft.Stack`
  that lays it over the card frame, so no view hand-rolls
  `background_screen(ft.Stack([...]))`.
- **Fault tolerance is built in (see §1.6).** Every provider is rendered through
  `guard`, so a failure in the header, content, actions, banner, overlay, or
  services degrades to the shared **Error Component** instead of crashing.
- **The card is always responsive.** Every card — compact or expanding alike —
  is centred and its width is CLAMPED to `[CARD_MIN_WIDTH, CARD_MAX_WIDTH]`
  against the window (`BaseView` re-clamps on `page.on_resized`): wide → caps at
  `CARD_MAX_WIDTH` (never stretches), narrow → shrinks to fit (the STRETCH card
  content makes the 400-px controls flex with it), always centred. A compact
  card's outer column AUTO-scrolls, so a tall form (Login/Signup) scrolls
  instead of clipping its bottom button.

**Login and Signup are visually identical to Welcome** (the design baseline):
same card frame, same H1 (`create_screen_heading`/`ui.heading`), same
`ELEMENT_SPACING`, same 400×70 buttons and 50%-white card. So is every other
screen in the app — `EXPAND_BODY` only changes whether that shared card hugs its
content or fills the screen and scrolls.

### 1.5.1 The declarative `ui` schema (`views/common/renderer.py`)

Providers return `ui.UIComponent` nodes — a small declarative vocabulary
(`ui.heading`, `ui.text`, `ui.primary_button`, `ui.secondary_button`, `ui.raw`,
…) — not raw `ft.Control`s. `ViewRenderer` turns them into the live Flet tree.
`ui.raw(control)` is a pure identity pass-through for stateful, pre-built
controls a view needs to keep a live reference to (inputs, image controls,
file pickers, mutable columns refreshed at runtime) — it changes nothing about
how the control renders, it just lets the declarative schema carry it.

## 1.6 Fault tolerance — the Error Component & the backstop

The app must never crash to a black/blank screen. Defence is **three layered
rings**, all funnelling to ONE shared **Error Component** (`error_component()` in
`screen.py`: a danger icon over the friendly Hebrew line *"אירעה שגיאה, אנא נסו
שוב"*, styled like every other card heading):

1. **Component ring — `guard(build_fn)`.** Wrap a risky sub-tree (e.g. one
   derived from fetched data) so its failure renders the Error Component in place
   instead of bubbling. `BaseView` runs every provider (`get_header`/
   `get_content`/`get_actions`/`get_status_banner`/`get_overlay`/`get_services`)
   through `guard` automatically — so "an error in any region" degrades, by
   construction, instead of crashing the screen.
2. **Screen ring — the router's `_safe_build`.** The factory that builds each
   view is wrapped; any `build()` that throws falls back to `error_view(...)` —
   the SAME Error Component, framed in the identical `SystemHubView` card (the
   one every screen renders inside) with a back-to-menu recovery action. Single
   source: the router no longer hand-rolls its own error card.
3. **Route ring — `_bare_fallback`.** If even the styled error view can't mount,
   a dependency-free bare `ft.View` with one `ft.Text` is shown. After this a
   blank page is unreachable.

Also: every `build()` assembles only static controls (data loads happen in
`on_mount`, with inline status banners), and each list row is built in its own
try/except, so one bad record is skipped — not fatal.

### Stack-aware back navigation

Back must return to the screen that ACTUALLY opened the current one. Since a
screen can be reached from several places (ChatView opens from both Discover and
Matches), a hard-coded `page.go(PARENT)` sends the user to the wrong place. Use
the stack-aware helpers in `views/common/navigation.py`:

- `back_button(page, label=…, fallback=…)` — a SECONDARY (blue-grey) button that
  pops ONE level off `page.views` (the router turns the implied `page.go` into an
  UNWIND, preserving the revealed view's state), or routes to `fallback` when the
  current screen is the stack root.
- `go_back(page, fallback=…)` — the same logic for views that need their own
  `on_click` wrapper (e.g. ChatView, which sets a `_closing` guard first).
- `back_to_menu_button(page)` stays for the explicit "חזור לתפריט הראשי" affordance
  (an UNWIND/RESET straight to `/menu`), distinct from "back one screen".

Prefer the stack-aware pop over `page.go(HARDCODED_PARENT)` whenever the user
expects "go back one screen".

---

## 2. Typography & Inputs

Text uses **only** the sizes from `DS.type` (`style/design_system.py`):

| Token | px | Use |
|---|---|---|
| `DS.type.h1` | 50 | screen titles |
| `DS.type.h2` | 25 | card/section titles, error-card headings, avatar initials |
| `DS.type.button` | 40 | button labels (lower per-button only when a long label must wrap) |
| `DS.type.input` | 25 | field labels, typed text, dropdown options, inline errors, status banners |
| `DS.type.body` | 16 | secondary lines only — meta lines, message previews, hints |
| `DS.type.small` | 13 | the smallest hints (e.g. "tap to change photo") |

`body`/`small` are for secondary hint lines — never for inputs or primary actions.

**All form inputs go through `components/inputs.py::create_hebrew_text_field`.**
It is the single source of input geometry: `rtl=True`,
`text_size=DS.type.input` (oversized typed text), `width=DS.sizing.input_w`,
a fixed 70px tap height (`DS.sizing.input_h`) for single-line fields
(multiline fields grow), `password`/`can_reveal_password` wired together, and the
RTL alignment rule below. **Never construct a raw `ft.TextField` in a view.**

```python
self._name = create_hebrew_text_field("שם מלא", hebrew_content=True, on_submit=…)
self._bio  = create_hebrew_text_field("קצת עליי", hebrew_content=True,
                                       multiline=True, min_lines=4, max_lines=8,
                                       max_length=1000)
self._email = create_hebrew_text_field("אימייל")        # Latin → stays LEFT-aligned
```

**Dropdowns** (gender, region, day/month/year) are deliberately preferred over
free-text for the 50+ audience — nothing to mistype. Use `MyProfileView._make_dropdown`
(oversized label + `text_size=DS.type.input`, fixed width). Birth date is three
dropdowns, never a calendar grid.

### 2.1 Shared content primitives (`src/components/`)

Beyond buttons and inputs, recurring UI atoms live in `components/` so a view
COMPOSES them and never hand-rolls the styling. Using the primitive IS complying.

| Primitive | Module | Use |
|---|---|---|
| `create_screen_heading(text, *, center=True)` | `typography.py` | the screen H1 — centres by default (the one heading rule, every screen alike); pass `center=False` only for a right-aligned in-body heading that is NOT the screen's title. **Never inline an `ft.Text(size=DS.type.h1, …)` heading in a view.** |
| `create_section_heading(text, *, center=False)` | `typography.py` | an H2 subsection heading (parity with the screen heading). |
| `create_field_error_label()` / `set_field_error(label, msg)` / `clear_field_errors(*labels)` | `feedback.py` | per-field validation error labels (colour `DS.palette.field_error`). Replaces every view-local `_make_error_label`/`_set_error`. |
| `create_status_banner(*, width=None)` → `(container, text)` / `show_status(banner, text, msg, *, ok, auto_hide_sec=0.0)` | `feedback.py` | the inline status banner + its async show/hide helper. Replaces every view-local status `Container` and `_show_status`. |
| `create_chat_bubble(text, *, mine)` | `chat.py` | a single chat bubble with the RTL-immune absolute side-anchoring. |
| `create_initial_avatar(name, *, diameter, online=None)` / `create_photo_avatar(src, name, *, diameter)` / `create_unread_badge(count)` | `avatars.py` | initials/photo avatars and the unread-count badge (Discover, Matches, peer profile). |
| `create_tile_card(content, *, on_click, height=None)` | `cards.py` | the full-width tappable member-row card (Discover feed, Matches threads). |
| `create_candidate_tile(name, meta, *, online, on_click)` | `discover.py` | a complete Discover candidate row (composes avatar + tile card). |
| `create_profile_field(label, value)` | `profile_fields.py` | a read-only label/value block (peer profile). |

All geometry these atoms use (`STATUS_BANNER_PADDING`, `BUBBLE_PADDING`,
`BUBBLE_RADIUS`, `LIST_TILE_PADDING`, the card-frame tokens like
`CONTENT_CARD_PADDING_TALL`) is defined ONCE in the Design System
(`DS.pad.*`/`DS.spacing.*` in `style/design_system.py`);
`screen.py` owns no re-exported geometry of its own — `BaseView` and the
components read the tokens directly.

---

## 3. The RTL Right-Alignment Formula (the inversion trap)

In this Flet build, `page.rtl=True` **flips** `CrossAxisAlignment.END` /
`MainAxisAlignment.END` to the **visual left**, and a `Row` renders its **first
child rightmost**. So aligning to `END` to mean "right" produces scattered,
left-leaning layouts (it bit Discover, the read-only profile, chat, and the photo
tiles). The reliable formula — apply it everywhere:

- **Columns:** `horizontal_alignment=ft.CrossAxisAlignment.STRETCH` (children span
  full width and right-align via their own `text_align`).
- **Text:** `text_align=ft.TextAlign.RIGHT` (absolute, RTL-immune) **plus**
  `rtl=True` for shaping. For Hebrew-content inputs, pass `hebrew_content=True`.
- **Rows:** put the right-hand anchor (avatar, photo thumbnail) **FIRST** in the
  `controls` list; give the text column `expand=True`. Never use `MainAxisAlignment`
  to push something left/right. Never set `rtl=False` to "fix" it — overrides
  don't take effect in this build.

```python
ft.Row(controls=[avatar, ft.Column([name, meta], expand=True,
                                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH)])
# → avatar FAR RIGHT, name/meta fill the space to its left.
```

**Chat bubbles are the one exception — and they go further, not back.** A bubble's
side is set with **absolute** container alignment: `ft.Alignment(1, 0)` (mine,
right) / `ft.Alignment(-1, 0)` (peer, left) on a full-width wrapper. Absolute
coordinates are immune to the RTL flip; do not rewrite this to `END`/`START`.

---

## 4. Action Hierarchy (color semantics)

Color carries meaning; it is never decorative. Two button primitives, two roles:

| Primitive | Color | Meaning | Examples |
|---|---|---|---|
| `create_primary_button` | `DS.palette.primary` (brand red) | **constructive** content actions | "שמור שינויים", "התחבר", "הירשם", "תמונות נוספות", "הוסף תמונה נוספת", "שלח" |
| `create_secondary_button` | `DS.palette.secondary` (blue-grey) | **secondary / session-exit / navigation** | "ביטול", "התנתק מהמערכת", "חזור", "חזור לתפריט הראשי", "הסר תמונה", "סגירה" |

- A save and a logout/back must **never** share a color — a divider separates them
  (see `MyProfileView`, `MainMenuView`, `ChatView`).
- Both primitives keep the 70px tap target (`DS.sizing.button_h`) and a
  centered, RTL-aware, bold label. `text_size` drops to `DS.type.input` only for
  long labels that must fit on the button.
- **No raw hex strings anywhere.** All colors come from `DS.palette`, including
  the presence dots (`online` = bright `GREEN_ACCENT_400`, deliberately *not*
  `success`; `offline` = `GREY_400`) and the chat bubbles (`bubble_self` =
  `GREEN_100`, `bubble_peer` = `GREY_200`).

Buttons render inline at the card's tail — the same single column as the header
and content (§1.5), never a separate bar. On an `EXPAND_BODY` screen, only the
*content* scrolls (or self-scrolls); the actions stay pinned at the card's
bottom edge, so the primary action and its status feedback are always one tap
away no matter how far the form has scrolled.

---

## 5. Status & feedback

Screens surface state through an **inline status banner** built by
`components/feedback.py::create_status_banner()` (a `DS.palette.success` green or
`DS.palette.danger` red fill), driven by the shared async
`show_status(banner, text, msg, *, ok, auto_hide_sec=0.0)` — never `page.snack_bar`
(unreliable across Flet versions) and never a hand-rolled per-view banner/helper.
Per-field validation uses `create_field_error_label()` (a hidden, RTL,
`DS.palette.field_error` label) adjacent to each field, set via
`set_field_error`/`clear_field_errors`, shown one-at-a-time (first failure wins,
so a senior isn't overwhelmed). Success banners auto-fade (`auto_hide_sec`); error
banners persist until the next action. Empty states ("עדיין אין שיחות", "עדיין אין
פרופילים להצגה") are a *state*, shown calmly in the banner — not an error.

---

## Profile picture rule (cross-cutting)

A profile picture is **never null**. `views/common/photos.py::resolve_main_photo`
returns `photo_urls[0]` when it's a usable non-empty string, else the bundled
`AssetPaths.DEFAULT_PROFILE_IMAGE` (`UNDEFINED_PROFILE.png`). Every avatar /
main-picture render goes through it (or, in the read-only peer views, the
shared length-guarded `views/common/peer_data.py::safe_photo_src`), so a missing photo shows the template — never
an empty `src` (which Flet draws as nothing). Image controls that render a
user-supplied `src` set an `error_content` fallback (initials or an icon) and sit
on a solid `bgcolor`, so a stale/unreadable path can never fail the render tree to
black.

---

## Black-screen elimination (UI side of the Peer Layout Boundary Rule)

Any screen showing untrusted/partial data (canonically `user_profile_view.py`, and
the `discover` / `matches` / `chat` feeds) must:

1. Read every field through a **total `_safe_*` accessor** (never raises).
2. Live in `background_screen(translucent_card(…))` with ONE `expand=True` scroll
   region; long text wraps and scrolls (`overflow=CLIP` on values) — it can't
   overflow the render tree.
3. Run the fetch in `asyncio.to_thread` wrapped in try/except, and on any
   failure/missing-data swap in a **styled Hebrew error card** inside the same
   shell — `build()` assembles only static controls and cannot throw.
4. Build each **list row in isolation** (`_candidate_tile` / `_thread_row` /
   `_bubble` in their own try/except) so one bad record is skipped, not fatal.

The router is the final backstop (see `ENGINEERING_CONTRACT.md` → two-layer
backstop): even a build that defies all of the above lands on a styled error card,
and failing that, a bare last-resort view — never a black page.

---

## Enforcement strategy (how we keep it consistent)

1. **Primitives over policy.** The rules are encoded in `create_hebrew_text_field`,
   `create_primary_button` / `create_secondary_button`, `background_screen` /
   `translucent_card`, `photo_thumb`, `resolve_main_photo` / `extra_photo_urls`,
   `back_to_menu_button`. Using them == complying.
2. **Review checklist** (PR template):
   - [ ] Screen is an Interface-First `BaseView`: it implements
         `get_header`/`get_content` (+ `get_actions`/`get_status_banner`/
         `get_overlay`/`get_services` as needed) and declares `EXPAND_BODY`/
         `BODY_LAYOUT` only when it deviates from the compact-card default. It
         does NOT override `build()`, construct `SystemHubView`/`background_screen`/
         `translucent_card` directly, or hand-roll its own card assembly.
   - [ ] Risky/data-derived sub-trees fenced with `guard(...)` so a render
         failure shows the Error Component, never a crash. (`get_*` providers are
         already guarded by the framework.)
   - [ ] Back goes via `back_button`/`go_back` (stack-aware), not `page.go(HARDCODED_PARENT)`.
   - [ ] Screen wrapped in `background_screen(translucent_card(...))`; no custom BG/padding.
   - [ ] All inputs via `create_hebrew_text_field`; text sizes ∈ {H1, H2, BUTTON, INPUT} for primary content.
   - [ ] Screen title via `create_screen_heading`; field errors via `create_field_error_label`/`set_field_error`; status via `create_status_banner` + `show_status` — no inline H1, error label, or status `Container` in the view.
   - [ ] Columns `STRETCH`; Text `text_align=RIGHT` + `rtl=True`; Row anchors first; chat bubbles use absolute `ft.Alignment(±1,0)`.
   - [ ] Buttons via the two button primitives; constructive = red, exit/nav = blue-grey, separated by a divider.
   - [ ] No raw hex; no raw `ft.TextField` / `ft.View`; colors from `DS.palette`.
   - [ ] Untrusted/feed data read via `_safe_*`; list rows built in isolated try/except; main picture via `resolve_main_photo`.
   - [ ] Status via the inline banner (SUCCESS/DANGER), not `page.snack_bar`.
3. **Audit grep** — these should return nothing in `src/views/` (except `_base.py`):
   - `ft.TextField(` (use the primitive) · `CrossAxisAlignment.END` · `MainAxisAlignment.END`
     · `rtl=False` · raw `#` hex color literals · `bgcolor=` on a top-level view container.
   - `def build(` (only `_base.py` defines it) · `size=DS.type.h1` (use `create_screen_heading`)
     · `_make_error_label` / `_show_status` (use the `feedback.py` primitives) · `padding=14`
     (use `DS.pad.status_banner`) · `ft.Colors.RED_ACCENT` (use `DS.palette.field_error`)
     · `auth_modal` / `auth_card` (deleted — Login is a plain `BaseView`, the same as Welcome).
4. **Status quo:** auth, menu, profile, additional-photos, discover, chat, matches,
   the read-only peer profile, the cold-boot spinner, and the router error view all
   comply and share the single card frame.
