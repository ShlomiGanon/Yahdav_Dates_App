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
- **Auth screens use the same shell.** `views/auth/widgets/auth_card.py::auth_modal`
  is a thin wrapper that centres a `translucent_card` inside `background_screen` —
  it is NOT a bespoke modal/scrim. Login & Signup look identical to every other
  screen.

**Enforcement:** a view that constructs a raw `ft.View` with its own `bgcolor`, or
hardcodes `padding=…` on a top-level container, fails review.

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

Screens surface state through an **inline status banner** (a colored
`translucent`-adjacent `Container` with a `ThemeColors.SUCCESS` green or
`ThemeColors.DANGER` red fill), never `page.snack_bar` (unreliable across Flet
versions). Per-field validation uses a hidden, RTL, red error label adjacent to
each field, shown one-at-a-time (first failure wins, so a senior isn't overwhelmed).
Success banners auto-fade (`auto_hide_sec`); error banners persist until the next
action. Empty states ("עדיין אין שיחות", "עדיין אין פרופילים להצגה") are a *state*,
shown calmly in the banner — not an error.

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
   - [ ] Screen wrapped in `background_screen(translucent_card(...))`; no custom BG/padding.
   - [ ] All inputs via `create_hebrew_text_field`; text sizes ∈ {H1, H2, BUTTON, INPUT} for primary content.
   - [ ] Columns `STRETCH`; Text `text_align=RIGHT` + `rtl=True`; Row anchors first; chat bubbles use absolute `ft.Alignment(±1,0)`.
   - [ ] Buttons via the two button primitives; constructive = red, exit/nav = blue-grey, separated by a divider.
   - [ ] No raw hex; no raw `ft.TextField` / `ft.View`; colors from `ThemeColors`.
   - [ ] Untrusted/feed data read via `_safe_*`; list rows built in isolated try/except; main picture via `resolve_main_photo`.
   - [ ] Status via the inline banner (SUCCESS/DANGER), not `page.snack_bar`.
3. **Audit grep** — these should return nothing in `src/views/`:
   - `ft.TextField(` (use the primitive) · `CrossAxisAlignment.END` · `MainAxisAlignment.END`
     · `rtl=False` · raw `#` hex color literals · `bgcolor=` on a top-level view container.
4. **Status quo:** auth, menu, profile, additional-photos, discover, chat, matches,
   the read-only peer profile, the cold-boot spinner, and the router error view all
   comply and share the single shell.
