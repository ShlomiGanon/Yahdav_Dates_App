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
  guard: a solid `bgcolor=ThemeColors.BACKGROUND` sits *behind* the image, so a
  missing/slow asset never falls through to an unset (black) page background.
  `app.py` also sets `page.bgcolor = ThemeColors.BACKGROUND` as a belt to that
  suspenders.
- **No view invents structural margins/padding.** Use `translucent_card`'s
  params. The opacity is `UIConstants.FORM_OVERLAY_OPACITY` (0.5), the radius is
  `UIConstants.CORNER_RADIUS`, the default padding is `UIConstants.CARD_PADDING`.
  One definition, tuned in one place.
- **Photo tiles** reuse `views/common/photos.py::photo_thumb(src, size=…)` — the
  single rounded/clipped image tile with a broken-image `error_content` fallback.
- **Auth screens use the same shell.** Login, Signup and Welcome are ordinary
  `ScreenType.HUB` `BaseView`s (§1.5) — there is NO bespoke auth modal/scrim. They
  declare `SCREEN_TYPE = ScreenType.HUB` and provide `get_body`/`get_actions`, so
  they render the identical centered card as every other hub screen.

**Enforcement:** a view that constructs a raw `ft.View` with its own `bgcolor`, or
hardcodes `padding=…` on a top-level container, fails review.

---

## 1.5 The Interface-First screen framework

Every screen is an **Interface-First** `BaseView`: it DECLARES what it is and
PROVIDES its pieces through fixed methods — it never writes `build()` and never
touches layout. The framework (`BaseView.build()` + `ScreenShell` in
`views/common/screen.py`) orchestrates everything: assembly, centering,
responsiveness, lifecycle binding, and a built-in error catch-all.

A screen DECLARES (class attributes):

- `ROUTE` — its route string.
- `SCREEN_TYPE` — `ScreenType.HUB` (centered single card; Welcome/Login/Signup/
  Menu/placeholder) or `ScreenType.CONTENT` (scroll card + sticky animated bar;
  everything else). Default CONTENT.
- `BODY_LAYOUT` — `BodyLayout.SCROLLING` (default) or `SELF_SCROLLING` when the
  body is its own `ft.ListView`.

A screen PROVIDES (override what it needs):

- `get_body() -> ft.Control` — REQUIRED. The content as ONE composed control.
- `get_actions() -> list[ft.Control]` — buttons (HUB → inside the card; CONTENT →
  the sticky bar). Default `[]`.
- `get_status_banner() -> ft.Control | None` — CONTENT inline banner. Default None.
- `get_overlay() -> ft.Control | None` — CONTENT fullscreen layer (lightbox). Default None.
- `get_services() -> list` — Flet services (e.g. an `ft.FilePicker`). Default `[]`.

```python
class MyProfileView(BaseView):
    ROUTE = "/profile/me"                       # SCREEN_TYPE defaults to CONTENT

    def get_body(self) -> ft.Control:           # the view composes its OWN content
        ...                                     # (inner arrangement = view's job)
        return ft.Column([heading, *fields], spacing=CONTENT_BODY_SPACING,
                         horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def get_actions(self):  return [save_button, divider, back_to_menu_button(self.page)]
    def get_status_banner(self): return self._status_banner
    def get_services(self): return [self._file_picker]
```

The hard SoC line is **framework = outer frame; view = inner composition** — the
view arranges its own content; the Shell never reaches in. The four providers are
handed to `ScreenShell` as builders, so a failure in any of them degrades to the
shared Error Component (§1.6) instead of crashing.

The Shell exposes **no** layout knobs (`body_alignment`, `actions_alignment`,
raw `scroll`, `card_padding` are gone from the contract). The one scroll choice
is expressed by INTENT via `body_layout=BodyLayout.SELF_SCROLLING` (the body is
an `ft.ListView` that owns its scroll), not a raw flag. The Buttons Area height
is deterministic (auto-summed from the actions, override via `action_bar_height`)
and `animate`d, so it expands/contracts smoothly when a mounted view swaps its
actions via `set_actions(action_bar_of(view), [...])`.

```
┌──────────────────────────────────────┐
│  translucent_card (expand=True)       │  ← the ONLY region that scrolls:
│   title + body                        │     heading + form / feed / messages
└──────────────────────────────────────┘
┌──────────────────────────────────────┐
│  transparent action bar (sticky)      │  ← OUTSIDE the card, never scrolls:
│   [status banner]  [buttons …]        │     status feedback + ALL buttons
└──────────────────────────────────────┘
```

Hard rules, all encoded in the primitive:

- **The content card scrolls; the action bar does not.** Only the card holds
  `scroll`/an `expand=True` `ListView`; the buttons stay on-screen however far
  the body scrolls. A back button **inside** the card on a content screen fails
  review.
- **All buttons live in the action bar, OUTSIDE the card.** The bar is
  transparent (`bgcolor=TRANSPARENT`) so the buttons float on the BG.
- **Status banners belong in the action bar, never in the scroll region** — pass
  them as `status_banner=…`; the primitive pins them above the buttons so
  save/error/empty-state feedback is always visible.
- **Primary (red) vs secondary/navigation (blue-grey) are separated by a
  divider** (see §4). The geometry — margins, padding, spacing, expand behaviour
  — is defined ONCE in `screen.py` (`CONTENT_CARD_MARGIN`, `CONTENT_CARD_PADDING`,
  `CONTENT_CARD_PADDING_TALL`, `ACTION_BAR_PADDING`, …); views never re-invent it.
- **The Buttons Area animates.** It is a single persistent container with an
  explicit, action-derived `height` + `animate`; cross-screen heights stay
  consistent (no jump) and intra-screen action changes tween. A non-button
  action (divider, send-row) should declare its own `.height` so the auto-sum
  stays tight.
- **Canonical top-logo clearance.** The Shell applies one card padding
  (`CONTENT_CARD_PADDING_TALL`) to EVERY content screen, so no view passes a
  `card_padding`; the heading clears the BG's top logo uniformly app-wide.
- **Overlays belong to the Shell.** A fullscreen layer (e.g. the peer album's
  lightbox) is passed as `overlay=…`; the Shell owns the `ft.Stack`, so no view
  hand-rolls `background_screen(ft.Stack([...]))`.
- **Fault tolerance is built in (see §1.6).** `body`, each `action`, and
  `overlay` may be a control OR a zero-arg builder; the Shell runs builders
  through `guard`, so a section that fails to construct degrades to the shared
  **Error Component** instead of crashing the screen.
- **Responsive hub card.** The HUB card is centred both axes and its width is
  CLAMPED to `[CARD_MIN_WIDTH, CARD_MAX_WIDTH]` against the window
  (`BaseView` re-clamps on `page.on_resized`): wide → caps at `CARD_MAX_WIDTH`
  (never stretches), narrow → shrinks to fit (the STRETCH card content makes the
  400-px controls flex with it), always centred. The centred column AUTO-scrolls,
  so a tall form (Login/Signup) scrolls instead of clipping its bottom button.
- **Internal building blocks:** `content_screen(...)` / `content_layout(...)`
  remain only as the low-level back-compat helpers (and for the layout tests);
  no view calls them — every content screen builds through `ScreenShell`.

**Hub / auth / status screens (`SCREEN_TYPE = ScreenType.HUB`) share the SAME
unified `ScreenShell` — the HUB branch.** Welcome, Main Menu, Login, Signup, the
"coming soon" placeholder, **and the router's own boot spinner + error view**
(via the `hub_screen(...)` back-compat shim) all render ONE translucent card,
centred both axes, every control (buttons included) INSIDE the card. No
scroll/action-bar split, no custom backgrounds or top-level padding, and
no hand-rolled `background_screen(translucent_card(…))` assembly anywhere. The
centring + card geometry is defined once in `screen.py`. **Login and Signup are
visually identical to Welcome** (the design baseline): same hub frame, same H1
(`create_screen_heading`), same `ELEMENT_SPACING`, same 400×70 buttons and
50%-white card.

## 1.6 Fault tolerance — the Error Component & the backstop

The app must never crash to a black/blank screen. Defence is **three layered
rings**, all funnelling to ONE shared **Error Component** (`error_component()` in
`screen.py`: a danger icon over the friendly Hebrew line *"אירעה שגיאה, אנא נסו
שוב"*, styled like every other card heading):

1. **Component ring — `guard(build_fn)`.** Wrap a risky sub-tree (e.g. one
   derived from fetched data) so its failure renders the Error Component in place
   instead of bubbling. `ScreenShell` accepts `body` / `actions` / `overlay` as
   controls OR zero-arg builders and runs builders through `guard` automatically
   — so "an error in the body or actions" degrades, by construction.
2. **Screen ring — the router's `_safe_build`.** The factory that builds each
   view is wrapped; any `build()` that throws falls back to `error_screen(...)` —
   the SAME Error Component, framed as a full `hub_screen` view with a
   back-to-menu recovery action. Single source: the router no longer hand-rolls
   its own error card.
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

Text uses **only** the sizes from `TextSizes` (`utils/constants.py`):

| Token | px | Use |
|---|---|---|
| `TextSizes.H1` | 50 | screen titles |
| `TextSizes.H2` | 25 | card/section titles, error-card headings, avatar initials |
| `TextSizes.BUTTON` | 40 | button labels (lower per-button only when a long label must wrap) |
| `TextSizes.INPUT` | 25 | field labels, typed text, dropdown options, inline errors, status banners |
| `TextSizes.BODY` | 16 | secondary lines only — meta lines, message previews, hints |
| `TextSizes.SMALL` | 13 | the smallest hints (e.g. "tap to change photo") |

`BODY`/`SMALL` are for secondary hint lines — never for inputs or primary actions.

**All form inputs go through `components/inputs.py::create_hebrew_text_field`.**
It is the single source of input geometry: `rtl=True`,
`text_size=TextSizes.INPUT` (oversized typed text), `width=UIConstants.INPUT_WIDTH`,
a fixed 70px tap height (`UIConstants.INPUT_HEIGHT`) for single-line fields
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
(oversized label + `text_size=TextSizes.INPUT`, fixed width). Birth date is three
dropdowns, never a calendar grid.

### 2.1 Shared content primitives (`src/components/`)

Beyond buttons and inputs, recurring UI atoms live in `components/` so a view
COMPOSES them and never hand-rolls the styling. Using the primitive IS complying.

| Primitive | Module | Use |
|---|---|---|
| `create_screen_heading(text, *, center=False)` | `typography.py` | the screen H1. `center=True` for HUB/auth screens; default RIGHT for content screens. **Never inline an `ft.Text(size=TextSizes.H1, …)` heading in a view.** |
| `create_section_heading(text, *, center=False)` | `typography.py` | an H2 subsection heading (parity with the screen heading). |
| `create_field_error_label()` / `set_field_error(label, msg)` / `clear_field_errors(*labels)` | `feedback.py` | per-field validation error labels (colour `ThemeColors.FIELD_ERROR`). Replaces every view-local `_make_error_label`/`_set_error`. |
| `create_status_banner(*, width=None)` → `(container, text)` / `show_status(banner, text, msg, *, ok, auto_hide_sec=0.0)` | `feedback.py` | the inline status banner + its async show/hide helper. Replaces every view-local status `Container` and `_show_status`. |
| `create_chat_bubble(text, *, mine)` | `chat.py` | a single chat bubble with the RTL-immune absolute side-anchoring. |
| `create_initial_avatar(name, *, diameter, online=None)` / `create_photo_avatar(src, name, *, diameter)` / `create_unread_badge(count)` | `avatars.py` | initials/photo avatars and the unread-count badge (Discover, Matches, peer profile). |
| `create_tile_card(content, *, on_click, height=None)` | `cards.py` | the full-width tappable member-row card (Discover feed, Matches threads). |
| `create_candidate_tile(name, meta, *, online, on_click)` | `discover.py` | a complete Discover candidate row (composes avatar + tile card). |
| `create_profile_field(label, value)` | `profile_fields.py` | a read-only label/value block (peer profile). |

All geometry these atoms use (`STATUS_BANNER_PADDING`, `BUBBLE_PADDING`,
`BUBBLE_RADIUS`, `LIST_TILE_PADDING`, the `CONTENT_*`/`ACTION_BAR_*` frame tokens)
is defined ONCE in `UIConstants` (`utils/constants.py`); `screen.py` re-exports the
frame tokens it shares with views (e.g. `CONTENT_BODY_SPACING`).

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
| `create_primary_button` | `ThemeColors.PRIMARY` (brand red) | **constructive** content actions | "שמור שינויים", "התחבר", "הירשם", "תמונות נוספות", "הוסף תמונה נוספת", "שלח" |
| `create_secondary_button` | `ThemeColors.SECONDARY` (blue-grey) | **secondary / session-exit / navigation** | "ביטול", "התנתק מהמערכת", "חזור", "חזור לתפריט הראשי", "הסר תמונה", "סגירה" |

- A save and a logout/back must **never** share a color — a divider separates them
  (see `MyProfileView`, `MainMenuView`, `ChatView`).
- Both primitives keep the 70px tap target (`UIConstants.BUTTON_HEIGHT`) and a
  centered, RTL-aware, bold label. `text_size` drops to `TextSizes.INPUT` only for
  long labels that must fit on the button.
- **No raw hex strings anywhere.** All colors come from `ThemeColors`, including
  the presence dots (`ONLINE` = bright `GREEN_ACCENT_400`, deliberately *not*
  `SUCCESS`; `OFFLINE` = `GREY_400`) and the chat bubbles (`BUBBLE_SELF` =
  `GREEN_100`, `BUBBLE_PEER` = `GREY_200`).

The standard screen footer is a **sticky bottom action bar** (transparent, sits
outside the scroll region) so the primary action and its status feedback are
always one tap away no matter how far the form has scrolled.

---

## 5. Status & feedback

Screens surface state through an **inline status banner** built by
`components/feedback.py::create_status_banner()` (a `ThemeColors.SUCCESS` green or
`ThemeColors.DANGER` red fill), driven by the shared async
`show_status(banner, text, msg, *, ok, auto_hide_sec=0.0)` — never `page.snack_bar`
(unreliable across Flet versions) and never a hand-rolled per-view banner/helper.
Per-field validation uses `create_field_error_label()` (a hidden, RTL,
`ThemeColors.FIELD_ERROR` label) adjacent to each field, set via
`set_field_error`/`clear_field_errors`, shown one-at-a-time (first failure wins,
so a senior isn't overwhelmed). Success banners auto-fade (`auto_hide_sec`); error
banners persist until the next action. Empty states ("עדיין אין שיחות", "עדיין אין
פרופילים להצגה") are a *state*, shown calmly in the banner — not an error.

---

## Profile picture rule (cross-cutting)

A profile picture is **never null**. `views/common/photos.py::resolve_main_photo`
returns `photo_urls[0]` when it's a usable non-empty string, else the bundled
`AssetPaths.DEFAULT_PROFILE_IMAGE` (`UNDEFINED_PROFILE.png`). Every avatar /
main-picture render goes through it (or, in the read-only peer view, the
length-guarded `_safe_photo_src`), so a missing photo shows the template — never
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
   - [ ] Screen is an Interface-First `BaseView`: it implements `get_body()`
         (+ `get_actions`/`get_status_banner`/`get_overlay`/`get_services` as
         needed) and declares `SCREEN_TYPE`/`BODY_LAYOUT`. It does NOT override
         `build()`, call `ScreenShell`/`hub_screen`/`content_screen` directly, or
         hand-roll `background_screen(translucent_card(…))`.
   - [ ] Risky/data-derived sub-trees fenced with `guard(...)` so a render
         failure shows the Error Component, never a crash. (`get_*` providers are
         already guarded by the framework.)
   - [ ] Back goes via `back_button`/`go_back` (stack-aware), not `page.go(HARDCODED_PARENT)`.
   - [ ] Screen wrapped in `background_screen(translucent_card(...))`; no custom BG/padding.
   - [ ] All inputs via `create_hebrew_text_field`; text sizes ∈ {H1, H2, BUTTON, INPUT} for primary content.
   - [ ] Screen title via `create_screen_heading`; field errors via `create_field_error_label`/`set_field_error`; status via `create_status_banner` + `show_status` — no inline H1, error label, or status `Container` in the view.
   - [ ] Columns `STRETCH`; Text `text_align=RIGHT` + `rtl=True`; Row anchors first; chat bubbles use absolute `ft.Alignment(±1,0)`.
   - [ ] Buttons via the two button primitives; constructive = red, exit/nav = blue-grey, separated by a divider.
   - [ ] No raw hex; no raw `ft.TextField` / `ft.View`; colors from `ThemeColors`.
   - [ ] Untrusted/feed data read via `_safe_*`; list rows built in isolated try/except; main picture via `resolve_main_photo`.
   - [ ] Status via the inline banner (SUCCESS/DANGER), not `page.snack_bar`.
3. **Audit grep** — these should return nothing in `src/views/` (except `_base.py`):
   - `ft.TextField(` (use the primitive) · `CrossAxisAlignment.END` · `MainAxisAlignment.END`
     · `rtl=False` · raw `#` hex color literals · `bgcolor=` on a top-level view container.
   - `def build(` (only `_base.py` defines it) · `size=TextSizes.H1` (use `create_screen_heading`)
     · `_make_error_label` / `_show_status` (use the `feedback.py` primitives) · `padding=14`
     (use `UIConstants.STATUS_BANNER_PADDING`) · `ft.Colors.RED_ACCENT` (use `ThemeColors.FIELD_ERROR`)
     · `auth_modal` / `auth_card` (deleted — Login is a plain HUB `BaseView`).
4. **Status quo:** auth, menu, profile, additional-photos, discover, chat, matches,
   the read-only peer profile, the cold-boot spinner, and the router error view all
   comply and share the single shell.
