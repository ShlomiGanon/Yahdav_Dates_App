# Backend Plan — Express + TypeScript + SQLite

> **Status:** ✅ All Phases Complete (1–5)
> **Architecture:** MVC — Models · Controllers · Routes
>
> | Phase | Scope | Status |
> |-------|-------|--------|
> | 1 | Foundation (config, DB, migrations, Express app, errorHandler) | ✅ Done |
> | 2 | Query Ledger, Models (User, Session), Auth routes (`/auth/*`) | ✅ Done |
> | 3 | Profile + Photos routes (`/users/*`), storageService, ProfileModel | ✅ Done |
> | 4 | Chat routes (`/chat/*`) + WebSocket server + pushService | ✅ Done |
> | 5 | Admin routes (`/admin/*`) | ✅ Done |
>
> **Implementation notes (differs from original plan):**
> - SQLite driver: `node:sqlite` (built-in, Node 25) instead of `better-sqlite3` (fails to compile on Node 25)
> - `/conversations/*` renamed to `/chat/*` to match mobile API contract
> - Discover pagination: page-based (`?page&limit`) instead of cursor-based
> - No separate controllers layer — handler logic lives directly in route files

---

## 1. Overview

Node.js / Express / TypeScript backend. Three layers:
- **Models** — SQLite queries + business logic per domain
- **Controllers** — HTTP handlers; call models, return JSON
- **Routes** — wire URLs to controllers; apply middleware in order

---

## 2. Technology Stack

| Component | Library |
|-----------|---------|
| Runtime | Node.js 20 LTS |
| Framework | Express 4 |
| Language | TypeScript 5 |
| SQLite | `better-sqlite3` 9 |
| WebSocket | `ws` 8 |
| JWT | `jsonwebtoken` 9 |
| Validation | `express-validator` 7 |
| File uploads | `multer` 1 |
| Password | `bcrypt` 5 |
| Push | Expo Push API (HTTP) |
| Config | `dotenv` 16 |
| Dev runner | `tsx watch` |
| Testing | `jest` + `supertest` |

---

## 3. Folder Structure

```
backend/src/
├── server.ts               # HTTP entry — creates app, attaches WS
├── app.ts                  # middleware, routes, error handler
├── config.ts               # typed env config
│
├── database/
│   ├── connection.ts       # better-sqlite3 + WAL pragmas
│   ├── migrate.ts          # versioned SQL runner
│   └── queries/            # QUERY LEDGER — all SQL lives here
│       ├── auth.queries.ts
│       ├── profile.queries.ts
│       └── messaging.queries.ts
│
├── models/                 # data + business logic; no HTTP
│   ├── UserModel.ts
│   ├── ProfileModel.ts
│   ├── MessageModel.ts
│   └── SessionModel.ts
│
├── controllers/            # HTTP handlers; no SQL
│   ├── auth.controller.ts
│   ├── profile.controller.ts
│   ├── messaging.controller.ts
│   ├── photos.controller.ts
│   └── admin.controller.ts
│
├── routes/                 # Express routers
│   ├── auth.routes.ts
│   ├── profile.routes.ts
│   ├── messaging.routes.ts
│   ├── photos.routes.ts
│   └── admin.routes.ts
│
├── middleware/
│   ├── authenticate.ts     # JWT verify → req.user
│   ├── requireAdmin.ts     # checks req.user.is_admin
│   └── errorHandler.ts     # global error handler
│
├── websocket/
│   ├── wsServer.ts         # attaches ws.Server to HTTP
│   ├── wsManager.ts        # Map<userId, WebSocket>
│   └── wsHandlers.ts       # message frame handlers
│
└── services/
    ├── pushService.ts      # Expo Push API
    └── storageService.ts   # multer config + file helpers

migrations/                 # 001_initial.sql, 002_*.sql ...
data/uploads/               # git-ignored runtime files
tests/                      # auth / profile / messaging / admin
```

---

## 4. MVC Responsibilities

**Models**
- Own all SQLite access via Query Ledger
- Contain business logic (e.g., discover excludes blocked users)
- Return typed objects; never touch `req` / `res`
- Synchronous (`better-sqlite3` is sync — no async/await)

**Controllers**
- Call model methods; map results to HTTP responses
- Apply `validationResult(req)` from express-validator
- No SQL, no business logic

**Routes**
- Middleware order: `authenticate` → validator chains → controller
- Mounted in `app.ts` under their path prefix

---

## 5. Database Schema

Existing schema preserved. Two new columns:
- `is_admin INTEGER NOT NULL DEFAULT 0` on `auth_credentials`
- `expo_push_token TEXT` on `user_profiles`

**Migration runner** (`migrate.ts`):
```
on startup:
  create schema_version table if missing
  read current version number
  apply *.sql files with higher version in order
  update version number
```

---

## 6. Query Ledger

All SQL in `database/queries/`. Models import from there — zero inline SQL anywhere else. Direct port of Python's `sqlite_queries.py`.

```
// queries/profile.queries.ts
ProfileQueries = {
  DISCOVER:  SELECT profiles WHERE not blocked + status active, paginated
  UPSERT:    INSERT OR UPDATE user_profiles
  GET_BY_ID: SELECT single profile by user_id
}

// models/ProfileModel.ts
ProfileModel.discover(viewerId, limit)
  → db.prepare(ProfileQueries.DISCOVER).all({ viewer_id, limit })
  → rows.map(hydrate)   // parse JSON columns into typed fields
```

---

## 7. API Specification

**Base URL:** `localhost:3000` dev / `api.yahdav.app` prod
**Auth header:** `Authorization: Bearer <access_token>` on 🔒 routes

### Auth (`/auth`)

| Method | Path | Body / Query | Response |
|--------|------|-------------|----------|
| POST | `/auth/signup` | `{ email, username, password }` | 201 `{ user_id, access_token, refresh_token }` |
| POST | `/auth/login` | `{ identifier, password }` | 200 same · 401 wrong creds |
| POST | `/auth/refresh` | `{ refresh_token }` | 200 `{ access_token, refresh_token }` rotated |
| POST | `/auth/logout` | `{ refresh_token }` | 204 |
| GET 🔒 | `/auth/me` | — | 200 `{ user_id, email, username, is_admin }` |

### Profile (`/users`)

| Method | Path | Notes |
|--------|------|-------|
| GET 🔒 | `/users/me` | Full UserProfile |
| PUT 🔒 | `/users/me` | Partial update → updated UserProfile |
| GET 🔒 | `/users/discover` | `?limit&cursor` → `{ users[], next_cursor }` |
| GET 🔒 | `/users/:id` | PeerProfile (public fields only) · 404 if missing |
| POST 🔒 | `/users/:id/block` | 204 |
| POST 🔒 | `/users/me/device-token` | `{ expo_token }` → 204 |

### Photos (`/users/me/photos`)

| Method | Path | Notes |
|--------|------|-------|
| POST 🔒 | `/users/me/photos` | `multipart/form-data` · field `file` + `slot` (`"main"/"extra"`) → `{ photo_url, photo_urls[] }` |
| DELETE 🔒 | `/users/me/photos/:slot_index` | → `{ photo_urls[] }` |

Limits: 8 MB · `.jpg .jpeg .png .webp .heic` · UUID filename · 413 / 415 / 422

### Messaging (`/conversations`)

| Method | Path | Notes |
|--------|------|-------|
| GET 🔒 | `/conversations` | `{ conversations[] }` with unread counts |
| GET 🔒 | `/conversations/:peer_id/messages` | `?limit&cursor` → `{ messages[], next_cursor }` |
| POST 🔒 | `/conversations/:peer_id/messages` | REST fallback · `{ content, msg_type }` → 201 |
| POST 🔒 | `/conversations/:peer_id/read` | 204 |

### Admin (`/admin`) 🔒🛡️

Requires `is_admin = 1` on all routes.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/admin/users` | `?limit&offset&search` → `{ total, users[] }` |
| GET | `/admin/users/:id` | Full user detail (no password hash) |
| PUT | `/admin/users/:id/status` | `{ status }` → updated summary |
| DELETE | `/admin/users/:id` | 204 |

### WebSocket (`/ws`)

**Connect:** `ws://host/ws?token=<access_token>` — invalid token → close 4001

```
Client → Server:
  { type:"message", peer_id, content, msg_type }
  { type:"ping" }

Server → Client:
  { type:"message", message_id, sender_id, content, created_at }
  { type:"ack", message_id }
  { type:"error", code, detail }
  { type:"pong" }
```

Delivery: save to DB → peer online → WS · peer offline → push notification

---

## 8. Auth Design

**Tokens:**
- Access: 15-min JWT · payload `{ sub, is_admin, type:"access" }`
- Refresh: 30-day JWT · hash stored in `user_sessions` table

**Middleware:**
```
authenticate.ts:
  read Authorization: Bearer <token>
  → jwt.verify(token, JWT_SECRET)
  → attach { sub, is_admin } to req.user → next()
  → missing or invalid → 401
```

**Password:** `bcrypt` salt rounds 12. Replaces Python scrypt — equivalent security.

**Token rotation:** Each refresh deletes old session + inserts new. Reusing a revoked token → 401.

---

## 9. WebSocket Manager

```
wsManager (singleton)
  connections: Map<userId, WebSocket>

  .register(userId, ws)
  .unregister(userId)
  .isOnline(userId) → boolean
  .send(userId, data) → no-op if not connected
```

---

## 10. Push Service

```
pushService.send(expoToken, senderName, preview, peerId)
  → POST exp.host/push/send
    { to, title:"הודעה חדשה", body:"${senderName}: ${preview}",
      data:{ peer_id, screen:"chat" }, sound:"default" }
  → fire-and-forget; errors logged, never thrown
```

---

## 11. File Storage

```
multer diskStorage:
  destination: UPLOADS_DIR
  filename:    uuid() + ext(mimetype)
  limits:      8 MB, images only (jpg/png/webp/heic)

served at: GET /uploads/:file  →  express.static(UPLOADS_DIR)

storageService.deleteFile(path) → fs.unlink
  (swap to S3: replace this service only)
```

---

## 12. Configuration

```
PORT=3000
DB_PATH=data/yahdav.sqlite3
UPLOADS_DIR=data/uploads
JWT_SECRET=<required — app throws if missing>
JWT_ACCESS_TTL=15m
JWT_REFRESH_TTL_DAYS=30
ADMIN_CORS_ORIGIN=http://localhost:5173
EXPO_PUSH_URL=https://exp.host/--/api/v2/push/send
```

---

## 13. Dev Setup

```bash
cd APP/backend
npm install
cp .env.example .env    # fill in JWT_SECRET
npm run migrate         # apply SQL migrations
npm run dev             # tsx watch — :3000
```

Scripts: `dev` · `build` · `start` · `migrate` · `test`

---

## 14. FastAPI → Express Comparison

| Concern | FastAPI (old plan) | Express (this plan) |
|---------|-------------------|---------------------|
| Language | Python | TypeScript |
| Architecture | Layered services | MVC |
| DB driver | `aiosqlite` (async) | `better-sqlite3` (sync) |
| Validation | Pydantic | `express-validator` |
| Password | scrypt | `bcrypt` |
| WebSocket | FastAPI WebSocket | `ws` |
| File uploads | `python-multipart` | `multer` |
| Query pattern | Query Ledger (Python) | Query Ledger (TypeScript) |
| Migrations | Versioned SQL | Versioned SQL |
