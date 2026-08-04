# Yahdav — Project Overview

יחדיו is a Hebrew-language Jewish dating app. It runs as three separate applications that communicate over HTTP and WebSocket:

- **Backend** — Node.js / Express API server (the single source of truth)
- **Admin Dashboard** — React web app for administrators to manage users
- **Mobile App** — React Native (Expo) app for iOS and Android end-users

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Mobile App (iOS / Android)          Admin Dashboard (Web)   │
│  React Native + Expo SDK 57          React 18 + Vite         │
│                                                              │
│  REST over HTTPS        WebSocket    REST over HTTPS         │
└──────────────┬──────────────┬──────────────┬────────────────┘
               │              │              │
               ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│           Backend — Node.js 20 + Express 4 + TypeScript      │
│                                                              │
│  /auth/*       /users/*      /chat/*      /admin/*           │
│  /uploads/:f   ws:/ws?token= (WebSocket endpoint)            │
│                                                              │
│  ┌──────────────┐    ┌───────────────────────────────────┐  │
│  │  SQLite WAL  │    │  data/uploads/  (photo files)     │  │
│  │  (one file)  │    │  (swap to S3 by changing one svc) │  │
│  └──────────────┘    └───────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## The Three Parts

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

**Auth:** Access token in React state; refresh token in `localStorage`. On page reload the interceptor silently calls `/auth/refresh` to restore the session. On 401 it retries once, then forces logout.

**RTL:** `<html dir="rtl">` in `index.html` — Tailwind CSS flips layout automatically.

**Runs on:** `localhost:5173` (dev) / `admin.yahdav.app` (prod, served by nginx)

---

### 3. Mobile App (`APP/mobile/`)

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

All three parts share the same token pair. The backend issues both; the mobile and admin consume them independently.

```
POST /auth/login { identifier, password }
  ← { access_token (15 min JWT), refresh_token (30 day JWT) }

POST /auth/refresh { refresh_token }
  ← { access_token, refresh_token }   ← token is rotated (old one revoked)

POST /auth/logout { refresh_token }
  ← 204
```

Every protected request sends `Authorization: Bearer <access_token>`.  
When the access token expires the axios interceptor (in both mobile and admin) automatically calls `/auth/refresh`, then retries the original request — transparent to the screen/page.

Admin-only routes additionally check `is_admin = 1` in the JWT payload. Non-admin users get `403`.

---

### REST API — Key Endpoints

| Prefix | Who uses it | What it does |
|--------|-------------|--------------|
| `POST /auth/*` | Mobile + Admin | Signup, login, refresh, logout |
| `GET/PUT /users/me` | Mobile | Read/update own profile |
| `POST /users/me/photos` | Mobile | Upload extra photos |
| `GET /users/discover` | Mobile | Paginated candidate feed |
| `GET /users/:id` | Mobile | Read peer profile |
| `POST /users/:id/block` | Mobile | Block a user |
| `POST /users/me/push-token` | Mobile | Register Expo push token after login |
| `GET /chat/conversations` | Mobile | Conversation thread list |
| `GET /chat/:peer_id` | Mobile | Message history (cursor-paginated) |
| `POST /chat/:peer_id` | Mobile | Send message (REST fallback) |
| `PUT /chat/:peer_id/read` | Mobile | Mark thread as read |
| `GET /admin/users` | Admin | Paginated user list with search |
| `GET /admin/users/:id` | Admin | Full user detail |
| `PUT /admin/users/:id/status` | Admin | Change user status |
| `DELETE /admin/users/:id` | Admin | Delete user |
| `GET /uploads/:filename` | Mobile + Admin | Serve uploaded photo files |

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
  → POST /users/me/push-token { token, platform }

When a message is sent and recipient is offline (server):
  POST https://exp.host/--/api/v2/push/send
    { to: expo_token, title: "הודעה חדשה", body: "...", data: { peer_id } }

On notification tap (mobile):
  RootNavigator reads data.peer_id from the notification payload
  → navigateToChat(peer_id, peer_name) via global navigationRef
  Works for: foreground tap, background tap, cold-start tap

On logout (mobile):
  DELETE /users/me/push-token  (parallel with POST /auth/logout)
```

---

## Data Flow — Key User Journeys

### First Login

```
Mobile                          Backend                        SQLite
  │                                │                              │
  ├─ POST /auth/signup ────────────►                              │
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
  ├─ GET /users/discover?page=1 ───►
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
  ├─ GET /users/:peer_id ──────────►
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
| Backend runtime | Node.js 20 LTS |
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
| Mobile framework | React Native + Expo SDK 57 |
| Mobile navigation | React Navigation v6 |
| Mobile token storage | Expo SecureStore |
| Mobile HTTP | Axios + JWT interceptor |
| Mobile push | `expo-notifications` |
| Dates (all apps) | `date-fns` with Hebrew locale |

---

## Folder Structure

```
APP/
├── project.md           ← this file
├── MASTER_PLAN.md       ← architecture decisions + remaining missions
├── remove_docker.md     ← record of Docker removal + how to run without it
│
├── backend/
│   ├── BACKEND_PLAN.md
│   ├── src/             ← Express app source (TypeScript)
│   ├── migrations/      ← versioned SQL files
│   ├── tests/           ← 40 integration tests (supertest)
│   ├── data/            ← SQLite file + uploads/ (runtime, not committed)
│   ├── .env.example     ← template for production .env
│   └── package.json
│
├── admin/
│   ├── ADMIN_PLAN.md
│   ├── src/             ← React app source (TypeScript)
│   ├── dist/            ← production build output (runtime, not committed)
│   ├── nginx.conf       ← nginx SPA config for production server
│   ├── .env.example     ← template for .env.local
│   └── package.json
│
└── mobile/
    ├── MOBILE_PLAN.md
    ├── src/             ← React Native app source (TypeScript)
    ├── app.json         ← Expo config (bundle IDs, splash, icons)
    ├── eas.json         ← EAS Build profiles (dev / preview / production)
    └── package.json
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

Runs on `http://localhost:3000`. Health check: `GET /health` → `{ ok: true }`.

### 2 — Start the admin dashboard

```
cd APP/admin
npm install
cp .env.example .env.local   # VITE_API_BASE_URL=http://localhost:3000
npm run dev                   # Vite dev server
```

Runs on `http://localhost:5173`. Login requires an account with `is_admin = 1`.

### 3 — Start the mobile app

```
cd APP/mobile
npm install
npx expo start    # opens Expo dev tools — scan QR with Expo Go
```

Set `EXPO_PUBLIC_API_BASE_URL=http://<your-local-IP>:3000` in `eas.json` (development profile) or `app.json` extra — Expo Go on a physical device cannot reach `localhost`.

### 4 — Run backend tests

```
cd APP/backend
npm test    # 40 tests, in-memory SQLite, ~20 s
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
| `ADMIN_CORS_ORIGIN` | No | `http://localhost:5173` | Admin dashboard origin for CORS |
| `EXPO_PUSH_URL` | No | Expo default | Expo push API endpoint |

### Admin (`.env.local`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_API_BASE_URL` | **Yes** | Backend URL (`http://localhost:3000` dev / `https://api.yahdav.app` prod) |

### Mobile

Set via `eas.json` build profiles or `app.json` extra:

| Variable | Purpose |
|----------|---------|
| `EXPO_PUBLIC_API_BASE_URL` | Backend URL (dev: local IP, prod: `https://api.yahdav.app`) |

---

## What Is Left To Do

The code is complete and all 40 backend tests pass. The remaining work is operational — deploying to a real server and publishing to the app stores. See **MASTER_PLAN.md → Section 10** for the 10 remaining missions with detailed step-by-step instructions.

Quick summary:

| Mission | What |
|---------|------|
| 1 | Provision server, domain (`yahdav.app`), SSL, nginx |
| 2 | Install Node.js + PM2 on server, deploy backend |
| 3 | Build admin `dist/`, configure nginx on server |
| 4 | Create first admin account in production DB |
| 5 | Run `eas init` in `APP/mobile/`, fill in Expo project ID |
| 6 | Enroll Apple Developer, build + submit iOS app |
| 7 | Create Google Play account, build + submit Android app |
| 8 | Device testing — RTL, push, WebSocket, deep links |
| 9 | Set up daily SQLite backup to off-server storage |
| 10 | Set up uptime monitoring + alerts for `/health` |
