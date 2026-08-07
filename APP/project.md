# Yahdav — Project Overview

יחדיו is a Hebrew-language Jewish dating app. It runs as four separate
applications that communicate over HTTP and WebSocket, plus one shared
logic package that isn't a runtime service of its own:

- **Backend** — Node.js / Express API server (the single source of truth)
- **Admin Dashboard** — React web app for administrators to manage users
- **Web App** — React web app for end-users (browser)
- **Mobile App** — React Native (Expo) app for iOS and Android end-users
- **Shared** — pure-TypeScript package holding logic common to the
  end-user clients (validation rules, session/routing decisions, i18n
  copy, typed API clients, the canonical page/screen registry) and, for
  validation and copy, the backend too. See `architecture.md` and
  `shared/README.md` for how it's structured and consumed.

---

## System Architecture

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

`shared` isn't pictured — it's a library, not a runtime service. It sits
beside Web and Mobile (both import its `.ts` source directly, transpiled
by their own bundler) and is a real compiled npm dependency of Backend.

---

## The Parts

### 1. Backend (`APP/backend/`)

Express REST API + WebSocket server. All business logic lives here.

**Key responsibilities:**
- Authenticate users (JWT access + refresh tokens)
- Serve and mutate user profiles and photos
- Run the discover feed (filtered, paginated candidates)
- Store and deliver chat messages
- Deliver push notifications when a chat recipient is offline
- Expose admin endpoints guarded by `is_admin = 1`

**Architecture pattern: MVC**
```
Routes → Middleware → Route handlers → Models → Query Ledger → SQLite
```

- `src/database/queries/` — all SQL in one place; nothing else touches SQL directly
- `src/models/` — business logic; never sees `req`/`res`
- `src/routes/` — HTTP wiring; handlers live inside route files
- `src/middleware/` — `authenticate.ts` (JWT → `req.user`), `requireAdmin.ts`
- `src/websocket/` — WS server, connection registry, message handlers
- `src/services/` — push notifications (Expo Push API), file storage (multer)
- `migrations/` — versioned `.sql` files applied automatically on startup

**Runs on:** `localhost:3000` (dev) / `api.yahdav.app` (prod)

---

### 2. Admin Dashboard (`APP/admin/`)

Single-page React app. Admins use it to view, search, suspend, and delete user accounts.

**Key responsibilities:**
- Login with an account that has `is_admin = 1`
- Browse and search the full user list (paginated)
- View any user's full profile detail
- Change a user's status (active / suspended / banned)
- Delete a user account

**Architecture pattern: Registry-driven sections**
```
SECTION_REGISTRY → Sidebar nav items + React Router routes
```

Adding a new admin section = create one folder under `src/sections/`, add one entry to `_registry.ts`. No other files change.

**Auth:** Access token in React state; refresh token in `localStorage`. On page reload the interceptor silently calls `/api/auth/refresh` to restore the session. On 401 it retries once, then forces logout.

**RTL:** `<html dir="rtl">` in `index.html` — Tailwind CSS flips layout automatically.

**Runs on:** `localhost:5173` (dev) / `admin.yahdav.app` (prod, served by nginx)

---

### 3. Web App (`APP/web/`)

React web app for end-users — the browser counterpart to the mobile app.
Hebrew-first, RTL everywhere. Every page defined in
`shared/pages/pageIds.ts` is routed and fully built, at feature parity
with mobile's equivalent screens except where a deliberate,
web-appropriate UX difference applies (see below and `architecture.md`).

**Key responsibilities:**
- Register and login
- Edit own profile — text fields, main photo, and extra photos
- Browse the discover feed, view peer profiles (including their extra
  photos), block users
- Real-time chat via WebSocket, as a single master-detail view
  (`ChatMasterDetail.tsx`) rather than mobile's two separate screens —
  both the `chatHistory` and `chat` pages render it, one WebSocket per
  mount feeding both the conversation list and the open thread

**Architecture pattern: Pages → typed API clients → Backend**
```
Pages (pure UI, state held inline — no hooks layer) → api/client.ts
(typed factories from @shared/api) → Backend
```

No page calls `axios` directly — all network calls go through
`api/client.ts`'s `authApi` / `usersApi` / `chatApi` singletons.

**Auth:** Access token in `sessionStorage`; refresh token in
`localStorage`. The axios response interceptor auto-refreshes on
`{success:false, error:'unauthorized'}` (see the Authentication section
below for why it isn't a 401 check) and retries the original request.

**RTL:** `<html dir="rtl">` — Tailwind CSS flips layout automatically.

**Runs on:** `localhost:5174` (dev, fixed port in `vite.config.ts`)

---

### 4. Mobile App (`APP/mobile/`)

React Native Expo app for end-users. Hebrew-first, RTL everywhere.

**Key responsibilities:**
- Register and login
- Edit own profile (text fields + photos)
- Browse the discover feed and view peer profiles
- Block users
- Real-time chat via WebSocket; push notifications when offline
- Tap a push notification to open the correct chat screen

**Architecture pattern: Screens → Hooks → API modules**
```
Screens (pure UI) → custom hooks (data + state) → api/ (typed HTTP calls) → Backend
```

No screen calls `axios` directly — all network calls go through `api/users.ts` or `api/chat.ts`.

**Auth:** Access token in memory; refresh token in Expo SecureStore. On cold start `useAutoLogin.ts` reads SecureStore and silently refreshes before showing any screen.

**RTL:** `I18nManager.forceRTL(true)` in `main.tsx` once, before first render.

**Runs on:** Expo Go (dev) / App Store + Google Play (prod)

---

## How the Parts Connect

### Authentication

All three client apps share the same token pair shape. The backend issues both; mobile, web, and admin each consume them independently, storing them wherever fits their own platform (Expo SecureStore, `sessionStorage`/`localStorage`, and React state/`localStorage` respectively).

```
POST /api/auth/login { identifier, password }
  ← { access_token (15 min JWT), refresh_token (30 day JWT) }

POST /api/auth/refresh { refresh_token }
  ← { access_token, refresh_token }   ← token is rotated (old one revoked)

POST /api/auth/logout { refresh_token }
  ← 204
```

Every protected request sends `Authorization: Bearer <access_token>`.  
When the access token expires, each client's axios interceptor (mobile, web, and admin all have one) automatically calls `/api/auth/refresh`, then retries the original request — transparent to the screen/page. The backend never uses HTTP 401 for this; it always answers 200 with `{success:false, error:'unauthorized'}` in the body, which is what each interceptor actually checks for.

Admin-only routes additionally check `is_admin = 1` in the JWT payload. Non-admin users get `403`.

---

### REST API — Key Endpoints

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

Every backend endpoint lives under `/api/*` — composed in one router,
`backend/src/routes/api.routes.ts`, mounted at `/api` in `app.ts`. This
became necessary once the backend started also serving the web and admin
frontends as static files from this same origin (see the CD pipeline in
`.github/workflows/release.yml`): the admin dashboard's own page routes
(`/admin/users`, `/admin/users/:id`) and web's own chat page route
(`/chat/:peer_id`) were string-identical to API paths that used to live
at root, which broke SPA-refresh behavior on those exact pages.
Namespacing the whole API under `/api` avoided that class of collision
permanently rather than resolving it prefix-by-prefix.

---

### WebSocket — Real-Time Chat

The mobile app opens a WebSocket connection when entering `ChatScreen` or `ChatHistoryScreen`.

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

**Delivery logic (server-side):**
1. Save message to SQLite
2. Is recipient currently connected? → deliver via WebSocket immediately
3. Recipient offline? → send Expo Push Notification

**Reconnect logic (mobile-side):** exponential backoff — 1 s → 2 s → 4 s … 30 s max, up to 10 attempts.

---

### Push Notifications

```
After login (mobile):
  requestPermissionsAsync()
  → getExpoPushTokenAsync()
  → POST /api/users/me/push-token { token, platform }

When a message is sent and recipient is offline (server):
  POST https://exp.host/--/api/v2/push/send
    { to: expo_token, title: "הודעה חדשה", body: "...", data: { peer_id } }

On notification tap (mobile):
  RootNavigator reads data.peer_id from the notification payload
  → navigateToChat(peer_id, peer_name) via global navigationRef
  Works for: foreground tap, background tap, cold-start tap

On logout (mobile):
  DELETE /api/users/me/push-token  (parallel with POST /api/auth/logout)
```

---

## Data Flow — Key User Journeys

### First Login

```
Mobile                          Backend                        SQLite
  │                                │                              │
  ├─ POST /api/auth/signup ────────►                              │
  │                                ├─ bcrypt hash password ──────►│ insert auth_credentials
  │                                ├─ create user_profiles row ──►│
  │                                ├─ issue JWT pair ─────────────►│ insert user_sessions
  │◄─ { access_token, refresh }────┤                              │
  │                                │                              │
  ├─ store refresh in SecureStore  │                              │
  ├─ store access in memory        │                              │
  ├─ navigate to MainStack         │                              │
```

### Discover Feed

```
Mobile                          Backend
  │                                │
  ├─ GET /api/users/discover?page=1►
  │   Bearer: access_token         │
  │                                ├─ query user_profiles
  │                                │  WHERE user_id NOT IN blocked list
  │                                │     AND status = 'active'
  │                                │     AND user_id != viewer
  │                                │  ORDER BY registered_at DESC
  │                                │  LIMIT 20 OFFSET 0
  │◄─ [ { user_id, name, ... } ] ──┤
  │                                │
  ├─ user taps row → bottom sheet  │
  ├─ user taps "פרופיל מלא"        │
  ├─ GET /api/users/:peer_id ──────►
  │◄─ { name, bio, photos, ... } ──┤
```

### Sending a Chat Message

```
Mobile (sender)          Backend              Mobile (recipient)
     │                      │                        │
     ├─ WS: { type:"message", peer_id, content }     │
     │       ──────────────►│                        │
     │                      ├─ save to DB            │
     │                      ├─ is peer online?       │
     │                      │  YES ─────────────────►│ WS: { type:"message", ... }
     │◄─ WS: { type:"ack" } ┤  NO → Expo Push        │ (notification arrives)
```

---

## Database — Tables

All data lives in one SQLite file (`data/yahdav.sqlite3`, WAL mode).

| Table | What it holds |
|-------|---------------|
| `auth_credentials` | `user_id`, `email`, `username`, bcrypt `password_hash`, `is_admin` |
| `user_profiles` | All profile data, JSON columns for structured fields, `expo_push_token` |
| `user_sessions` | Refresh token hashes (30-day TTL); one row per active session |
| `user_blocks` | Asymmetric block relationships (`blocker_id` → `blocked_id`) |
| `direct_messages` | Every message; `conversation_id` = sorted pair of user IDs |

**JSON columns in `user_profiles`:** `display_name_json` · `bio_json` · `looking_for_json` · `location_json` · `lifestyle_json` · `photo_urls_json`

Migrations are in `backend/migrations/*.sql` — applied automatically when the server starts via `migrate.ts`.

---

## Technology Stack

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
| Mobile HTTP | Axios + JWT interceptor |
| Mobile push | `expo-notifications` |
| Shared logic | Pure TypeScript, zero framework deps (`APP/shared/`) |
| Dates (all apps) | `date-fns` with Hebrew locale |

---

## Folder Structure

```
APP/
├── project.md           ← this file
├── architecture.md      ← design philosophy + structural map (the "how it thinks")
├── package.json          ← npm workspace root (members: backend, shared)
│
├── backend/
│   ├── src/             ← Express app source (TypeScript)
│   ├── migrations/      ← versioned SQL files
│   ├── data/            ← SQLite file + uploads/ (runtime, not committed)
│   ├── .env.example     ← template for production .env
│   └── package.json
│
├── admin/
│   ├── src/             ← React app source (TypeScript)
│   ├── dist/            ← production build output (runtime, not committed)
│   ├── nginx.conf       ← nginx SPA config for production server
│   ├── .env.example     ← template for .env.local
│   └── package.json
│
├── web/
│   ├── src/               ← React app source (TypeScript)
│   ├── next_missions.md   ← historical record of the (now-completed) page buildout
│   ├── dist/              ← production build output (runtime, not committed)
│   └── package.json
│
├── mobile/
│   ├── src/             ← React Native app source (TypeScript)
│   ├── app.json         ← Expo config (bundle IDs, splash, icons)
│   ├── eas.json         ← EAS Build profiles (dev / preview / production)
│   └── package.json
│
├── shared/
│   ├── api/            ← axios client factories (auth, users, chat)
│   ├── flow/           ← session/routing flow rules
│   ├── pages/          ← canonical PageId registry — the shared contract
│   │                     every client's routes/screens must implement
│   ├── validation/     ← signup/profile validation rules
│   ├── copy/           ← i18n message dictionaries (client/ + server/)
│   ├── theme/          ← design tokens
│   ├── types/, utils/
│   ├── README.md       ← this package's own conventions
│   └── package.json
│
└── tests/                ← all test suites, one folder per package
    ├── backend/
    ├── web/
    ├── mobile/
    ├── admin/
    └── shared/
```

---

## Running Locally

### 1 — Start the backend

```
cd APP/backend
npm install
cp .env.example .env     # fill in JWT_SECRET at minimum
npm run dev              # tsx watch — restarts on file change
```

Runs on `http://localhost:3000`. Health check: `GET /api/health` → `{ ok: true }`.

### 2 — Start the admin dashboard

```
cd APP/admin
npm install
cp .env.example .env.local   # VITE_API_BASE_URL=http://localhost:3000
npm run dev                   # Vite dev server
```

Runs on `http://localhost:5173`. Login requires an account with `is_admin = 1`.

### 3 — Start the web app

```
cd APP/web
npm install
npm run dev    # Vite dev server
```

Runs on `http://localhost:5174` (fixed port in `vite.config.ts`). Defaults
to `VITE_API_BASE_URL=http://localhost:3000` if unset — there's no
`.env.example` for web yet since the default already matches local dev.

### 4 — Start the mobile app

```
cd APP/mobile
npm install
npx expo start    # opens Expo dev tools — scan QR with Expo Go
```

Set `EXPO_PUBLIC_API_BASE_URL=http://<your-local-IP>:3000` in `eas.json` (development profile) or `app.json` extra — Expo Go on a physical device cannot reach `localhost`.

### 5 — Run the test suites

Each package's test suite lives under the top-level `APP/tests/` (see
Folder Structure above), run from its own package directory:

```
cd APP/backend && npm test    # integration tests, in-memory SQLite
cd APP/shared  && npm test    # pure-logic unit tests
cd APP/web     && npm test    # vitest
cd APP/mobile  && npm test    # jest
cd APP/admin   && npm test    # vitest
```

---

## Environment Variables

### Backend (`.env`)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `PORT` | No | `3000` | HTTP listen port |
| `DB_PATH` | No | `data/yahdav.sqlite3` | SQLite file path |
| `UPLOADS_DIR` | No | `data/uploads` | Photo upload directory |
| `JWT_SECRET` | **Yes** | — | Signs all JWTs; must be long + random |
| `JWT_ACCESS_TTL` | No | `15m` | Access token lifetime |
| `JWT_REFRESH_TTL_DAYS` | No | `30` | Refresh token lifetime in days |
| `ADMIN_CORS_ORIGIN` | No | `http://localhost:5173,http://localhost:5174` | Comma-separated allowed browser origins — despite the name, covers both the admin dashboard and the web app |
| `EXPO_PUSH_URL` | No | Expo default | Expo push API endpoint |

### Admin (`.env.local`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_API_BASE_URL` | **Yes** | Backend URL (`http://localhost:3000` dev / `https://api.yahdav.app` prod) |

### Web

No `.env.local` template exists yet — `VITE_API_BASE_URL` falls back to
`http://localhost:3000` if unset, which already matches local dev.

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_API_BASE_URL` | No | Backend URL (defaults to `http://localhost:3000`; set explicitly for prod) |

### Mobile

Set via `eas.json` build profiles or `app.json` extra:

| Variable | Purpose |
|----------|---------|
| `EXPO_PUBLIC_API_BASE_URL` | Backend URL (dev: local IP, prod: `https://api.yahdav.app`) |

---

## What Is Left To Do

Backend, admin, web, and mobile are all feature-complete — every page
`shared/pages/pageIds.ts` declares is routed and fully built on both web
and mobile, at feature parity except where a documented, deliberate UX
difference applies (see `architecture.md`). `web/next_missions.md` no
longer tracks any open work; it's kept only as a record of the buildout.

What remains is one open product decision, one code-quality item, and the
operational work of deploying to a real server and publishing to the app
stores:

| Area | What |
|------|------|
| Web photo resize (product decision) | Mobile downsizes photos client-side before upload (1080px longest edge, 0.8 JPEG quality via `expo-image-manipulator`); web currently uploads the original file as-is. Needs a decision on whether web should get an equivalent (e.g. Canvas-based) resize before this is built. |
| Mobile brace style (code quality) | Standardize Allman brace style across the entire mobile codebase — currently inconsistent (most of `mobile/src` is K&R-brace) despite `architecture.md` listing "Allman brace style throughout" as a project-wide leading principle. |
| Server | Provision server, domain (`yahdav.app`), SSL, nginx |
| Backend deploy | Install Node.js + PM2 on server, deploy backend |
| Backend hardening | No rate limiting (e.g. on `/api/auth/*`) and no security-headers middleware (e.g. `helmet`) are wired into `app.ts` yet |
| Admin deploy | Build admin `dist/`, configure nginx on server |
| Web deploy | Build web `dist/`, configure nginx/static hosting on server |
| Admin account | No seed/bootstrap script exists yet — create the first `is_admin = 1` account by hand in the production DB |
| Mobile (EAS) | Run `eas init` in `APP/mobile/` — `app.json`'s `projectId` is still the placeholder `REPLACE_WITH_EAS_PROJECT_ID` |
| iOS | Enroll Apple Developer, build + submit iOS app |
| Android | Create Google Play account, build + submit Android app |
| Device testing | RTL, push, WebSocket, deep links |
| Backups | Set up daily SQLite backup to off-server storage |
| Monitoring | Set up uptime monitoring + alerts for `/api/health` |
