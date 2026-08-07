# Architecture — יחדיו (Yahdav)

This is the single, comprehensive reference for how this codebase is built
and why. It replaces what used to be several scattered files
(`APP/architecture.md`, `APP/project.md`, `APP/review.md`,
`APP/shared/README.md`, `APP/web/README.md`, `APP/web/next_missions.md`)
— all consolidated here so there is one place to read, not five.

For open/future work, see [`BACKLOG.md`](./BACKLOG.md) in this same
folder. For running a packaged release locally or deploying it to a
server, see `APP/backend/docs/LOCAL_SETUP.md` and `REMOTE_SETUP.md` —
those stay next to the backend because they ship *inside* the release
package itself (see the CI/CD section below), not just as repo docs.

---

## 1. What the product is

יחדיו ("Together") is a Hebrew-language, RTL-first Jewish dating app. It
consists of four separate applications talking to one backend, plus one
shared logic package that is a library, not a runtime service of its own:

- **Backend** — Node.js/Express API server. The single source of truth
  for data and business rules. Nothing else touches the database.
- **Web App** — React app for end-users, browser-based.
- **Mobile App** — React Native (Expo) app for iOS and Android end-users.
- **Admin Dashboard** — React app for administrators to manage user
  accounts.
- **Shared** — pure-TypeScript package holding logic common to the
  end-user clients (validation rules, session/routing decisions, i18n
  copy, typed API clients, the canonical page/screen registry) and, for
  validation and copy, the backend too.

Current functional status: **backend, web, mobile, and admin are all
feature-complete** — every page the shared page registry declares is
routed and fully built on both web and mobile, at feature parity except
where a documented, deliberate UX difference applies (see §7). What
remains is operational (deployment, app store submission) and a handful
of known, tracked gaps — see `BACKLOG.md`.

---

## 2. System architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│  Mobile App          Web App             Admin Dashboard              │
│  React Native        React 19 + Vite     React 18 + Vite              │
│  + Expo SDK 57        (end-users)         (admins)                    │
│                                                                        │
│  REST + WebSocket    REST over HTTPS     REST over HTTPS              │
└──────────┬───────────────┬───────────────────┬───────────────────────┘
           │               │                   │
           ▼               ▼                   ▼
┌───────────────────────────────────────────────────────────────────────┐
│           Backend — Node.js 22 + Express 4 + TypeScript               │
│                                                                        │
│  /api/auth/*   /api/users/*  /api/chat/*  /api/admin/*                │
│  /api/uploads/:f  ws:/ws?token= (WebSocket endpoint)                  │
│                                                                        │
│  ┌──────────────┐    ┌───────────────────────────────────┐           │
│  │  SQLite WAL  │    │  data/uploads/  (photo files)      │           │
│  │  (one file)  │    │  (swap to S3 by changing one svc)  │           │
│  └──────────────┘    └───────────────────────────────────┘           │
└───────────────────────────────────────────────────────────────────────┘
```

The backend also serves the built web app (at `/`) and admin dashboard
(at `/admin`) as static files from the same origin — see §6.4 and the
CI/CD section for how that's assembled and why every backend API route
lives under `/api/*` as a result.

`shared` isn't pictured — it's a library, not a runtime service. Web and
mobile both import its `.ts` source directly, transpiled by their own
bundler; the backend consumes it as a real, compiled npm workspace
dependency (see §8).

None of the four apps talk to each other directly. All of them talk only
to the backend, over HTTP and, for chat, WebSocket.

---

## 3. Design philosophy

**Explicit over implicit.** The clearest expression of this is the API
contract: every backend response is HTTP 200, and success/failure lives
entirely in the response body (`{ success, message, error? }`), never in
the status code. This was a deliberate, discussed decision: HTTP status
codes conflate transport-level and business-level failure, and the system
wants them kept apart. The same instinct shows up everywhere else — a
machine-readable `error` code and a human-readable `message` are always
two separate fields, never one string doing double duty.

**Single source of truth, enforced by proof, not convention.** Wherever
the same fact could plausibly need to exist twice (a validation rule, a
piece of user-facing copy, a routing decision, a color, a page's own
identity), the system drives it into one place and makes every consumer
read from there. "Centralized" is never taken on faith — a full
mobile/web code-sharing audit (see §7) repeatedly caught things that
*weren't* actually centralized in practice, and each fix wasn't just
"make it match" but "make it structurally impossible to drift again" —
usually a test or a compiler error that fires the moment two copies
disagree. The page/screen inventory follows the same discipline:
`shared/pages/pageIds.ts` is the one place a page's identity (`profile`,
`discover`, …) is declared; every platform's own route table (web's
`pages/routes.ts`) or screen-name table (mobile's
`navigation/screenNames.ts`) is typed as `Record<PageId, ...>` via `as
const satisfies`, so adding a page to `shared` without updating both
platforms is a compile error, not a silent gap.

**Verify by running it, not by reading it.** A passing `tsc --noEmit` is
treated as necessary and never sufficient. Every change that crosses a
real execution boundary — a new shared module a bundler has to resolve, a
new package a Node runtime has to `require()`, a new CSS value a browser
has to render, a new CI workflow — gets proven by actually executing that
boundary: a live bundler request, a real compiled server booted and hit
with `curl`, a browser driven end-to-end, a real GitHub Actions run where
possible. The type checker catches shape; only running the thing catches
whether it actually resolves and behaves.

**Platform-idiomatic, not platform-uniform.** The three client apps don't
share UI, and they're not forced into an artificial common shape. Mobile
screens delegate their data and actions to custom hooks; web pages hold
the same kind of state inline, without a hooks layer; the admin panel is
organized as a registry of self-contained "sections." Each is the natural
idiom for its own framework. What *is* forced to be identical across
platforms is business meaning — the same validation rule, the same
routing decision, the same copy — never markup or component structure.
Section 7 documents several places where the audit explicitly recommended
*not* unifying UI that looked similar but served different purposes.

**Minimalism as a constraint, not an aesthetic.** No ORM — the backend
talks to SQLite through Node's own built-in `node:sqlite` driver with
hand-written parameterized SQL, not an abstraction layer. No barrel
files, anywhere, in any package. No abstraction introduced for a need
that doesn't exist yet. When two things look similar but serve different
purposes (e.g. a generic "fill in all fields" message versus a
field-specific one), they're kept as two things rather than collapsed
into one for the sake of tidiness.

---

## 4. Leading principles (load-bearing, not stylistic)

1. **Every backend response is HTTP 200.** Failure is `success: false` in
   the body, with a machine-readable `error` code and a separate
   human-readable `message`. Nothing downstream branches on status code
   (the one exception: `403` for a non-admin hitting an admin-only
   route — see §6.1).
2. **`shared` never imports a framework and never detects a platform.**
   No React/React Native/router imports; no `Platform.OS`, no `expo-*`
   checks. If shared logic needs platform-specific state or capability,
   the caller passes it in — shared code never reaches out for it. This
   was deliberately upheld even under pressure to reduce duplication
   further (see §7's chat-controller finding).
3. **Deep imports only.** Consumers import a specific module
   (`@shared/flow/authFlow`), never a barrel `index.ts`. There isn't one,
   in any package.
4. **One concept, one file, named after its main export.**
5. **Refresh tokens rotate on use and are stored hashed, never in
   plaintext.** A used or expired refresh token is rejected outright, not
   silently accepted.
6. **A passing type check is not proof of a working system.** Anything
   that crosses a real module-resolution or rendering boundary gets
   verified by actually executing it before it's considered done.
7. **Allman brace style throughout.** `{` always opens on its own line.
   Followed consistently in `backend/`, `shared/`, `web/`, and `admin/`.
   **Known exception:** most of `mobile/src` still uses K&R-style braces
   (`{` on the same line) — this predates the convention being made
   explicit and has not been retrofitted. New mobile code written since
   is Allman-style; old files were not swept. Tracked in `BACKLOG.md`.
8. **Every backend endpoint lives under `/api/*`.** See §6.1 for why.

---

## 5. Coding guidelines

- **No ORM.** Backend SQL is hand-written and parameterized, in
  `backend/src/database/queries/`. Nothing else touches SQL directly.
- **Shared-first for business logic.** If a validation rule, formatter,
  domain constant, or piece of copy would otherwise need to exist in more
  than one client, it belongs in `shared/`, not duplicated per platform.
  This is enforced by convention and by an ongoing audit discipline (§7),
  not by tooling that blocks duplication automatically.
- **No framework dependencies in `shared`.** No React, React Native,
  Express, `react-router`, `@react-navigation`. No reaching for
  `window`/`localStorage`/`SecureStore` directly, and no `Platform.OS` or
  `expo-*` detection — ever. If shared logic needs platform state or a
  capability check, the *caller* passes it in as a parameter
  (dependency injection), matching the pattern in `createAuthApi(client)`
  and `createApiClient(baseURL, tokenStorage, onAuthFailure)`.
- **Deep imports, no barrels.** `@shared/api/auth`, `@shared/flow/authFlow`
  — never a re-exporting `index.ts`.
- **One concept per file**, named after its main export.
- **Allman brace style** for all new code, everywhere (see §4, item 7 for
  the one known legacy exception).
- **Platform-idiomatic UI**, never a forced shared component layer — see
  §3 and §7.
- **No product/architecture decisions get made silently.** Established
  practice throughout this project's development: when an ambiguity or a
  real fork in approach is hit, it gets surfaced and confirmed before
  code is written, not resolved unilaterally. Deviations from an agreed
  plan are documented, not silently reconciled.

---

## 6. The backend

Express REST API + WebSocket server, in `APP/backend/`. All business
logic lives here.

**Key responsibilities:**
- Authenticate users (JWT access + refresh tokens)
- Serve and mutate user profiles and photos
- Run the discover feed (filtered, paginated candidates)
- Store and deliver chat messages
- Deliver push notifications when a chat recipient is offline
- Expose admin endpoints guarded by `is_admin = 1`
- Serve the built web app and admin dashboard as static files (same
  origin) once packaged for release — see §6.4 and the CI/CD section

**Architecture pattern — MVC, layered top to bottom:**
```
Routes → Middleware → Models → Query Ledger → SQLite
```
- `src/database/queries/` — all SQL in one place; nothing else touches
  SQL directly
- `src/models/` — business logic in plain functions; never sees
  `req`/`res`; returns DTOs shaped for the wire, never raw DB rows
- `src/routes/` — HTTP wiring; handlers live inside route files;
  composed into one router (`src/routes/api.routes.ts`) mounted at
  `/api` — see §6.1
- `src/middleware/` — `authenticate.ts` (JWT → `req.user`),
  `requireAdmin.ts`
- `src/websocket/` — WS server, connection registry, message handlers.
  Chat's WebSocket path reuses the exact same Model layer as REST — a
  message sent over the socket persists through the identical code a
  REST call would use. Realtime and REST are two transports over one
  business layer, not two divergent implementations.
- `src/services/` — push notifications (Expo Push API), file storage
  (multer)
- `src/utils/mountSpa.ts` — serves a built web/admin bundle as static
  files with SPA fallback (see §6.4)
- `migrations/` — versioned `.sql` files, applied automatically on
  startup via `migrate.ts`

**Runs on:** `localhost:3000` in dev. No production deployment exists yet
— see `BACKLOG.md`.

### 6.1 Why every endpoint lives under `/api/*`

This wasn't the original design. Originally the API was mounted directly
at root: `/auth/*`, `/users/*`, `/chat/*`, `/admin/*`, `/uploads/*`,
`/health`. Once the backend started also serving the web app (at `/`) and
admin dashboard (at `/admin`) as static files from the same origin (see
§6.4), two exact path collisions surfaced:

- The admin dashboard's own frontend page routes (`/admin/users`,
  `/admin/users/:id`) were string-identical to the admin API's paths.
- Web's own frontend chat page route (`/chat/:peer_id`) was
  string-identical to the chat API's message-history endpoint.

Both collisions broke SPA-refresh behavior on those exact pages — a
browser refresh on `/admin/users` would hit the JSON API instead of
getting the admin app's `index.html` back. Rather than resolve this
prefix-by-prefix (which would only be a matter of time before the next
collision), every API route was namespaced under `/api/*` — composed
into one router, `backend/src/routes/api.routes.ts`, mounted once at
`/api` in `app.ts`. `/admin` and `/chat` (bare) now belong entirely to
the frontends' own client-side routing.

### 6.2 Authentication

All three client apps share the same token pair shape. The backend
issues both; mobile, web, and admin each consume them independently,
storing them wherever fits their own platform.

```
POST /api/auth/login { identifier, password }
  ← { access_token (15 min JWT), refresh_token (30 day JWT) }

POST /api/auth/refresh { refresh_token }
  ← { access_token, refresh_token }   ← token is rotated (old one revoked)

POST /api/auth/logout { refresh_token }
  ← 204
```

Every protected request sends `Authorization: Bearer <access_token>`.
When the access token expires, each client's axios interceptor
(mobile, web, and admin all have one) automatically calls
`/api/auth/refresh`, then retries the original request — transparent to
the screen/page. The backend never uses HTTP 401 for this; it always
answers 200 with `{success:false, error:'unauthorized'}` in the body,
which is what each interceptor actually checks for.

Admin-only routes additionally check `is_admin = 1` in the JWT payload.
Non-admin users get `403` — the one deliberate exception to "always
200," since this is a genuine authorization boundary, not a business
outcome to render in-app.

*Where* a token physically lives is platform-specific by necessity —
`SecureStore` on mobile, a deliberate `sessionStorage`/`localStorage`
split on web, React state/`localStorage` on admin. But *what happens
next* — where a successful login sends you, where an expired session
sends you, whether a signup logs you in automatically (it doesn't, on
purpose) — is one small set of event/guard rules in `shared/flow/authFlow.ts`,
and each platform just translates a logical outcome ("home," "login")
into its own concrete route or screen name.

### 6.3 REST API — key endpoints

| Prefix | Who uses it | What it does |
|--------|-------------|--------------|
| `POST /api/auth/*` | Mobile + Web + Admin | Signup, login, refresh, logout |
| `GET/PUT /api/users/me` | Mobile + Web | Read/update own profile |
| `POST /api/users/me/photo` | Mobile + Web | Upload/replace the main profile photo |
| `POST /api/users/me/photos` | Mobile + Web | Upload extra photos |
| `GET /api/users/discover` | Mobile + Web | Paginated candidate feed |
| `GET /api/users/:id` | Mobile + Web | Read peer profile |
| `POST /api/users/:id/block` | Mobile + Web | Block a user |
| `POST /api/users/me/push-token` | Mobile | Register Expo push token after login (mobile-only feature — no web push) |
| `GET /api/chat/conversations` | Mobile + Web | Conversation thread list |
| `GET /api/chat/:peer_id` | Mobile + Web | Message history (cursor-paginated) |
| `POST /api/chat/:peer_id` | Mobile + Web | Send message (REST fallback if the WebSocket send fails) |
| `PUT /api/chat/:peer_id/read` | Mobile + Web | Mark thread as read |
| `GET /api/admin/users` | Admin | Paginated user list with search |
| `GET /api/admin/users/:id` | Admin | Full user detail |
| `PUT /api/admin/users/:id/status` | Admin | Change user status |
| `DELETE /api/admin/users/:id` | Admin | Delete user |
| `GET /api/uploads/:filename` | Mobile + Web + Admin | Serve uploaded photo files |
| `GET /api/health` | — | Uptime check, `{ ok: true }` |

### 6.4 Serving web and admin same-origin

The backend can serve the built web app (at `/`) and admin dashboard (at
`/admin`) as static files from its own `public/web/` and `public/admin/`
folders, via `backend/src/utils/mountSpa.ts` — static files plus an SPA
fallback (any unmatched GET under that prefix returns `index.html`
instead of 404, so client-side routing survives a hard refresh). This
mount is a no-op if those folders aren't populated — true during ordinary
backend-only local dev, where web and admin instead run their own
separate Vite dev servers. Only a packaged release (see the CI/CD
section) actually populates `public/`.

Two consequences of this same-origin setup, both already applied:
- Every backend API route needed to move under `/api/*` (§6.1).
- Admin's built assets need a `/admin/` base path
  (`admin/vite.config.ts`'s `base`, applied only for production builds —
  local `npm run dev` is unaffected), and admin's login route lives at
  `/admin/login`, not bare `/login`, since bare `/login` is claimed by
  web once both are same-origin.

### 6.5 WebSocket — real-time chat

```
Connect:  ws://host/ws?token=<access_token>
          Invalid token → server closes with code 4001

Mobile → Server:
  { type: "message", peer_id, content, msg_type }
  { type: "ping" }

Server → Mobile:
  { type: "message", message_id, sender_id, content, created_at }
  { type: "ack", message_id }
  { type: "pong" }
```

**Delivery logic (server-side):** save message to SQLite → is the
recipient currently connected? deliver via WebSocket immediately →
otherwise send an Expo push notification.

**Reconnect logic (client-side):** exponential backoff — 1s → 2s → 4s …
30s max, up to 10 attempts.

**Ack reconciliation:** when a message is sent optimistically over the
socket, the client needs to swap its temporary local ID for the
server-confirmed one once the `{type:"ack"}` frame arrives. Both mobile
and web implement this correctly today; the pure frame-classification
logic (distinguishing an ack/error/pong/message frame) is shared, in
`shared/utils/classifyChatSocketFrame.ts` — deliberately scoped to just
classification, with all stateful reaction (ref bookkeeping, `setState`)
staying platform-specific, consistent with §4's "no framework in shared"
rule.

### 6.6 Push notifications

```
After login (mobile):
  requestPermissionsAsync() → getExpoPushTokenAsync()
  → POST /api/users/me/push-token { token, platform }

When a message is sent and the recipient is offline (server):
  POST https://exp.host/--/api/v2/push/send
    { to: expo_token, title: "...", body: "...", data: { peer_id } }

On notification tap (mobile):
  RootNavigator reads data.peer_id from the notification payload
  → navigateToChat(peer_id, peer_name) via a global navigationRef
  Works for: foreground tap, background tap, cold-start tap

On logout (mobile):
  DELETE /api/users/me/push-token  (parallel with POST /api/auth/logout)
```

### 6.7 Database

All data lives in one SQLite file (`data/yahdav.sqlite3`, WAL mode,
foreign keys on, accessed via Node's built-in `node:sqlite` driver).

| Table | What it holds |
|-------|---------------|
| `auth_credentials` | `user_id`, `email`, `username`, bcrypt `password_hash`, `is_admin` |
| `user_profiles` | All profile data, JSON columns for structured fields, `expo_push_token` |
| `user_sessions` | Refresh token hashes (30-day TTL); one row per active session |
| `user_blocks` | Asymmetric block relationships (`blocker_id` → `blocked_id`) |
| `direct_messages` | Every message; `conversation_id` = sorted pair of user IDs |

JSON columns in `user_profiles`: `display_name_json`, `bio_json`,
`looking_for_json`, `location_json`, `lifestyle_json`, `photo_urls_json`.

Migrations live in `backend/migrations/*.sql`, applied automatically on
server startup.

---

## 7. The client apps

### 7.1 Web App (`APP/web/`)

React app for end-users, browser-based. Hebrew-first, RTL everywhere
(`<html dir="rtl">`, Tailwind flips layout automatically). Every page
defined in `shared/pages/pageIds.ts` is routed and fully built, at
feature parity with mobile except where documented UX differences apply
(below).

**Architecture pattern:** Pages (pure UI, state held inline — no hooks
layer) → typed API client singletons (`api/client.ts`, factories from
`@shared/api`) → Backend. No page calls `axios` directly.

**Auth:** access token in `sessionStorage`; refresh token in
`localStorage`. The axios response interceptor auto-refreshes on
`{success:false, error:'unauthorized'}` and retries the original
request.

**Deliberate UX differences from mobile** (not gaps — documented, chosen
divergences):
- **Menu** is a landing dashboard with descriptive cards, not mobile's
  3-button hub — web's `AppShell` sidebar already handles navigation, so
  Menu doesn't need to.
- **Chat** is a single master-detail view (`ChatMasterDetail.tsx`)
  merging what mobile splits into two screens (`ChatHistoryScreen` +
  `ChatScreen`), since a wide viewport has room for both panes at once.
  One WebSocket per mount feeds both the conversation list and the open
  thread.
- **Discover**'s peer-preview is a slide-in side panel, web's equivalent
  of mobile's bottom sheet.

**Runs on:** `localhost:5174` in dev (fixed port in `vite.config.ts`).

### 7.2 Mobile App (`APP/mobile/`)

React Native (Expo SDK 57) app for iOS and Android end-users. Hebrew-first,
RTL everywhere (`I18nManager.forceRTL(true)` in `main.tsx`, once, before
first render).

**Architecture pattern:** Screens (pure UI) → custom hooks (data + state)
→ `api/` modules (typed HTTP calls) → Backend. No screen calls `axios`
directly.

**Auth:** access token in memory; refresh token in Expo SecureStore. On
cold start, `useAutoLogin.ts` reads SecureStore and silently refreshes
before showing any screen.

**Dev-build runtime server URL (new).** Production mobile builds have
their API base URL baked in at build time, same as always. A separate CI
workflow (`release-dev.yml`, see the CI/CD section) can additionally
produce a dev-variant build (distinct bundle ID `com.yahdav.app.dev`,
distinct display name "יחדיו (Dev)") where the API base URL is instead
entered by the person running the app, at runtime, on every launch:

- `mobile/app.config.js` (a dynamic Expo config, replacing the old
  static `app.json`) switches bundle ID/display name based on
  `EXPO_PUBLIC_RUNTIME_API_URL_ENABLED`, set only by the dev workflow.
- `mobile/src/components/ServerUrlGate.tsx` sits above `AuthProvider` in
  `main.tsx`. In production it's a plain, hook-free passthrough — proven
  zero behavior change by a dedicated test. In a dev build, it shows a
  gate screen pre-filled from AsyncStorage, validates the entered address
  by hitting `/api/health` before proceeding, then calls
  `setBaseURL()` on the shared API client and mounts the rest of the app.
- `shared/api/client.ts`'s `createApiClient` exposes `setBaseURL(url)` —
  updates both `client.defaults.baseURL` and the separate closure
  variable the token-refresh call uses internally (a real bug the first
  version of this method had: updating only the client's defaults left
  refresh calls silently going to the old server after a switch). Web and
  admin never call this method; their base URL is static, as before.

### 7.3 Admin Dashboard (`APP/admin/`)

Single-page React app. Admins use it to view, search, suspend, and
delete user accounts.

**Architecture pattern:** registry-driven sections —
`SECTION_REGISTRY` drives both sidebar nav items and React Router routes.
Adding a new admin section means creating one folder under `src/sections/`
and adding one entry to `_registry.ts`; no other files change.

**Auth:** access token in React state; refresh token in `localStorage`.
On page reload, the interceptor silently calls `/api/auth/refresh` to
restore the session. `is_admin` is checked centrally, once, in
`AuthContext`'s session-restore path — not just at login — so a
demoted admin whose session still restores via refresh doesn't stay
authenticated client-side. `RequireAuth`/`RedirectIfAuthed` both also
check `is_admin` independently, as defense in depth.

**Runs on:** `localhost:5173` in dev.

### 7.4 What's genuinely *not* shared between clients, and why

A full mobile/web code-sharing audit (dated 2026-08-06, all findings
resolved the same day) examined every mobile screen/hook against its web
counterpart. Nearly everything found duplicated was extracted into
`shared/` (validation chains, formatters, domain constants, pagination
bookkeeping, API client factories, the block-user flow, chat frame
classification, and a sweep of ~25 duplicated Hebrew UI strings into
`shared/copy/client`). Two things were explicitly examined and
deliberately **not** unified:

- **Menu / dashboard screens.** Similarity is low by design — see §7.1.
  Forcing more sharing here would fight a deliberate, documented UX
  divergence.
- **`AuthContext` bootstrap/session-restore mechanics.** Conceptually
  similar goal ("restore a session on app start"), but the actual
  mechanics genuinely differ: mobile validates via `/api/auth/me`
  against a token it already trusts from SecureStore; web proactively
  rotates via `/api/auth/refresh` because `sessionStorage` doesn't
  survive a tab close the way SecureStore survives an app relaunch.
  Unifying this would mean encoding two different storage-lifetime
  assumptions into one abstraction — the over-engineering trap the
  audit's own rubric warns against.

The audit also explicitly declined to extend `shared/`'s no-framework
rule for the sake of consolidating the chat/discover/photo list
controllers (optimistic sends, pagination, ack reconciliation) into
shared React hooks — real duplication exists there, but only the pure,
React-free pieces (pagination constants, optimistic-message
construction) were extracted; the `useState`/`useEffect` wiring stayed
duplicated per platform, on the reasoning that taking on a `react`
dependency inside `shared/` is a deliberate architecture call, not
something to decide as a side effect of chasing line-count reduction.

---

## 8. The shared package (`APP/shared/`)

Pure TypeScript. Owns business logic that would otherwise have to exist
redundantly in multiple places: validation rules, auth/session routing
decisions, user-facing copy, typed API client factories, and design
tokens.

```
APP/shared/
    api/            axios client factories — client.ts (createApiClient),
                     auth.ts, users.ts, chat.ts
    types/           TS types — auth.ts, user.ts, api.ts, chat.ts
    utils/           pure utilities — formatDate.ts, calcAge.ts,
                     genderLabel.ts, formatCandidateMeta.ts,
                     formatConversationPreview.ts, chatPagination.ts,
                     discoverPagination.ts, createOptimisticMessage.ts,
                     classifyChatSocketFrame.ts, blockPeer.ts,
                     reconnectingSocket.ts, resolveMediaUrl.ts
    flow/            session/routing flow rules — authFlow.ts (event +
                     guard rules mapping to a logical AuthDestination,
                     never a concrete route/screen)
    pages/           the canonical page/screen registry — pageIds.ts
                     declares the full PageId union every end-user
                     client must implement; each platform maps every
                     PageId to its own concrete route path or screen
                     name via `as const satisfies Record<PageId, string>`
                     — adding a page here without updating both
                     platforms fails to compile. The admin panel is a
                     separate system and isn't part of this registry.
    validation/      signup/profile validation rules — credentials.ts,
                     profile.ts
    reference/       pure domain data (not logic) — genderOptions.ts,
                     regionOptions.ts — rendered by each platform's own
                     picker component
    copy/            i18n message dictionaries — client/ and server/,
                     kept fully separate, each with its own
                     locales/he.ts and resolver (clientMessage /
                     serverMessage)
    theme/           design tokens — colors.ts
    config.ts        cross-platform literals with no better home —
                     DEFAULT_API_BASE_URL, MAX_ADDITIONAL_PHOTOS, APP_NAME
    tsconfig.json    standalone TS config for typechecking in isolation
    jest.config.js   test runner config — test files live in
                     ../tests/shared, not colocated here
    package.json     also declares subpath `exports` and a `build`
                     script — the backend consumes this package as a
                     real npm dependency, not raw source
```

**Consumers, and why they differ:** web and mobile import this package's
`.ts` source directly — their bundlers (Vite, Metro) transpile it
themselves. The backend is different: it's a `tsc`-compiled Node
service, so it consumes the real compiled `dist/` output via an npm
workspace dependency (`APP/package.json` declares `backend` + `shared` as
workspace members). Run `npm run build` in `shared/` after any source
change before the backend picks it up.

**One exception to "consumers import source directly":** web's colors
don't live in a `.ts` file at all — they're Tailwind `@theme` CSS custom
properties in `web/src/index.css`, and CSS can't `import` a TypeScript
module. `theme/colors.ts` is still the source of truth (mobile imports it
directly; web's `index.css` values are hand-kept in sync), but that sync
is enforced by a test (`tests/shared/theme/colors.test.ts`) that parses
`index.css` and asserts every value matches — not by the compiler. This
is the model to follow whenever a value genuinely can't be shared through
the type system: write a test that parses both sources and asserts they
agree, rather than duplicating silently or forcing an awkward shared
abstraction.

**Standing conventions:**
1. Deep imports only, no barrel file.
2. Framework purity — no React/React Native/router imports, no
   `window`/`localStorage`/`SecureStore` reached for directly.
3. Never detect platform or device capability — no `Platform.OS`, no
   `expo-*` imports, ever.
4. One concept per file, named after its main export.
5. Allman brace style.

If you add a new subpath that isn't a flat file directly under one of
these folders (a `something/index.ts` rather than `something.ts`), add
an explicit entry to `package.json`'s `exports` map — the wildcard
fallback does a literal string substitution with no automatic
directory-index fallback, and silently breaks for directory-shaped
modules otherwise (this already bit `copy/client` and `copy/server` once,
caught by a real `require()` at test-run time, not by `tsc`).

---

## 9. Technology stack

| Layer | Technology |
|-------|------------|
| Backend runtime | Node.js 22 |
| Backend framework | Express 4 + TypeScript 5 |
| SQLite driver | `node:sqlite` (built-in, no native compile step) |
| WebSocket | `ws` 8 |
| Auth | `jsonwebtoken` + `bcrypt` |
| File uploads | `multer` (disk storage; swap to S3 by changing `storageService.ts` only) |
| Push | Expo Push API (wraps FCM + APNs) |
| Admin framework | React 18 + Vite + TypeScript |
| Admin routing | React Router v6 |
| Admin styling | Tailwind CSS (`dir="rtl"`) |
| Admin HTTP | Axios + JWT interceptor |
| Web framework | React 19 + Vite + TypeScript |
| Web routing | React Router v7 |
| Web styling | Tailwind CSS 4 (`dir="rtl"`) |
| Web token storage | `sessionStorage` (access) + `localStorage` (refresh) |
| Web HTTP | Axios + JWT interceptor |
| Mobile framework | React Native + Expo SDK 57 |
| Mobile navigation | React Navigation v6 |
| Mobile token storage | Expo SecureStore |
| Mobile local storage | `@react-native-async-storage/async-storage` (dev-build server URL only, §7.2) |
| Mobile HTTP | Axios + JWT interceptor |
| Mobile push | `expo-notifications` |
| Shared logic | Pure TypeScript, zero framework deps (`APP/shared/`) |
| Dates (all apps) | `date-fns` with Hebrew locale |

---

## 10. CI/CD pipeline

Three workflow files, in `.github/workflows/`, each fully self-contained
— none of them call into another workflow file.

### 10.1 `test.yml` — "CI Tests"

Triggers on push to `main` or `dev`, on any PR targeting `main`, and
manually (`workflow_dispatch`). Four independent jobs — `backend`,
`mobile`, `web`, `admin` — each installs its own dependencies (plus
`shared`'s, for the two that consume it as raw source) and runs its own
test suite. No deployment happens here.

### 10.2 `release.yml` — "CD Production"

Triggers on `release: published` (a real GitHub Release being
published). Jobs:
- **`verify-tests-passed`** — resolves the release's tag to an exact
  commit and refuses to proceed unless that exact commit has a passing
  **CI Tests** workflow run (matched by workflow *name*, so this filter
  has to stay in sync if `test.yml`'s `name:` ever changes again). A
  release tag can point at any commit, including one nobody ever ran CI
  against; this is the gate against that. Skipped (not failed) for
  pre-releases, which propagates a skip through the whole rest of the
  workflow.
- **`build-web`** / **`build-admin`** — build in parallel, each uploads
  its `dist/` as a workflow artifact, and passes `commit_sha` through as
  its own job output (`build-server` needs it but doesn't directly
  `need` `verify-tests-passed`, so it can't read that job's output
  without this relay).
- **`build-server`** — needs both of the above; builds the backend,
  downloads the web/admin artifacts, assembles
  `yahdav-server-<tag>.zip`, and uploads it directly to the Release.
- **`build-android`** — unsigned APK, built directly in the runner
  (`expo prebuild` + `./gradlew assembleRelease`; no EAS, no signing yet
  — see `BACKLOG.md`), uploaded to the same Release.
- **`build-ios`** — a disabled (`if: false`) placeholder job, already
  wired into the dependency graph, with prerequisites documented inline.
  See `BACKLOG.md`.

### 10.3 `release-dev.yml` — "CD Dev"

Triggers on `workflow_dispatch` only (manual). No `verify-tests-passed`
gate — a dev build is meant for fast, on-demand iteration, not a
CI-verified release commit, so every job here just uses `github.sha`
directly instead of resolving a tag. Jobs:
- **`ensure-dev-release`** — creates a rolling `dev-latest` pre-release if
  it doesn't already exist. `build-server` and `build-android-dev` both
  depend on this, which avoids a real race condition: without it, both
  could independently find the release missing and both try to create
  it, one failing.
- **`build-web`** / **`build-admin`** — same as `release.yml`'s, minus
  the `commit_sha` relay (nothing to relay from here).
- **`build-server`** — needs `build-web`, `build-admin`, *and*
  `ensure-dev-release`; assembles `yahdav-server-dev-latest.zip` and
  uploads it directly to the `dev-latest` Release (`--clobber`, so it
  replaces the previous run's asset).
- **`build-android-dev`** — same mechanism as production's
  `build-android`, but sets `EXPO_PUBLIC_RUNTIME_API_URL_ENABLED=true`
  before `expo prebuild`, producing the dev bundle ID/display name and
  runtime server-URL gate described in §7.2.

### 10.4 What a release package actually contains

```
yahdav-server-<version>/
├── dist/                 ← compiled backend
├── migrations/           ← versioned SQL, applied automatically on startup
├── public/
│   ├── web/               ← built web app (served at /)
│   └── admin/              ← built admin dashboard (served at /admin)
├── docs/
│   ├── LOCAL_SETUP.md      ← how to run this package locally
│   └── REMOTE_SETUP.md     ← how to deploy it to a real server
├── package.json
├── package-lock.json
└── .env.example
```

Deliberately **not** included: `node_modules/` (installed by the person
running it), any real `.env`, any database file, any uploaded photos.
Full instructions for both scenarios live in
`APP/backend/docs/LOCAL_SETUP.md` and `REMOTE_SETUP.md` — those two files
ship inside every release package, which is why they live next to the
backend rather than in this `docs/` folder.

---

## 11. Environment variables

### Backend (`.env`)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `PORT` | No | `3000` | HTTP listen port |
| `DB_PATH` | No | `data/yahdav.sqlite3` | SQLite file path |
| `UPLOADS_DIR` | No | `data/uploads` | Photo upload directory |
| `WEB_PUBLIC_DIR` / `ADMIN_PUBLIC_DIR` | No | `public/web` / `public/admin` | Built frontend bundles served same-origin (§6.4) |
| `JWT_SECRET` | **Yes** | — | Signs all JWTs; must be long + random |
| `JWT_ACCESS_TTL` | No | `15m` | Access token lifetime |
| `JWT_REFRESH_TTL_DAYS` | No | `30` | Refresh token lifetime in days |
| `ADMIN_CORS_ORIGIN` | No | `http://localhost:5173,http://localhost:5174` | Comma-separated allowed browser origins — despite the name, covers both admin and web |
| `DOMAIN` | No | — | Not read by the app anywhere; a documentation placeholder for when a real domain exists (nginx/SSL config) |
| `EXPO_PUSH_URL` | No | Expo default | Expo push API endpoint |

### Admin (`.env.local`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_API_BASE_URL` | **Yes** | Backend URL |

### Web

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_API_BASE_URL` | No | Backend URL (defaults to `http://localhost:3000`) |

### Mobile

| Variable | Purpose |
|----------|---------|
| `EXPO_PUBLIC_API_BASE_URL` | Backend URL, baked in at build time (production builds) |
| `EXPO_PUBLIC_RUNTIME_API_URL_ENABLED` | Set only by `release-dev.yml` — switches on the dev-build runtime server-URL gate (§7.2) instead |

---

*For open and future work, see [`BACKLOG.md`](./BACKLOG.md).*
