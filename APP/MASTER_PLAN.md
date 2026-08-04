# Yahdav Dates App — Master Architecture Plan

> **Status:** ✅ All Phases Complete (1–6)
> **Goal:** Replace the Flet desktop app with Express backend, React admin dashboard, and React Native mobile app.

---

## 1. System Architecture

```
CLIENT LAYER
  ├── Mobile App (React Native / Expo)  ── REST + WebSocket ──┐
  └── Admin Dashboard (React / TS)      ── REST ──────────────┤
                                                              ▼
BACKEND LAYER — Express / Node.js / TypeScript
  ├── Auth Router       ├── Profiles Router
  ├── Messaging Router  ├── Admin Router
  ├── WebSocket Manager └── Expo Push Service

DATA LAYER
  ├── SQLite (data/yahdav.sqlite3) — WAL mode
  └── File Storage (data/uploads/) — S3-ready interface
```

---

## 2. Technology Stack

| Tier | Choice |
|------|--------|
| Backend | Node.js 20 + Express 4 + TypeScript |
| Database | SQLite WAL mode |
| Auth | JWT access + refresh tokens |
| Push | Expo Push API (wraps FCM + APNs) |
| Admin | React 18 + TypeScript + Vite |
| Mobile | React Native (Expo SDK) + TypeScript |
| HTTP client | Axios — JWT auto-refresh interceptor |

---

## 3. Key Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Database | SQLite retained — same schema, WAL mode |
| 2 | Auth | Two-token JWT: 15-min access + 30-day refresh with rotation |
| 3 | Chat | WebSocket in-app; Expo Push when offline |
| 4 | Admin | Separate React app; `/admin/*` requires `is_admin = 1` |
| 5 | Storage | Abstracted interface — swap local → S3 by changing one service |
| 6 | Language | Hebrew-first; UTF-8 API; `I18nManager.forceRTL` mobile; `dir="rtl"` admin |

---

## 4. Domain Model

| Table | Role |
|-------|------|
| `auth_credentials` | Login credentials, bcrypt hash, `is_admin` flag |
| `user_profiles` | Profile data, JSON sub-objects, `expo_push_token` |
| `user_sessions` | JWT refresh tokens (30-day TTL) |
| `user_blocks` | Asymmetric block relationships |
| `direct_messages` | Messages, cursor-paginated by `conversation_id` |

**JSON columns:** `display_name_json` · `bio_json` · `looking_for_json` · `location_json` · `lifestyle_json` · `photo_urls_json`

---

## 5. Auth Flow

```
POST /auth/login { identifier, password }
  → verify bcrypt → issue tokens
  ← { access_token, refresh_token }

All protected requests: Authorization: Bearer <access_token>

POST /auth/refresh { refresh_token }
  → validate → delete old session → create new (rotated)
  ← { access_token, refresh_token }

POST /auth/logout { refresh_token }
  → delete session row → 204
```

---

## 6. Chat Flow

```
WS connect: ws://host/ws?token=<jwt>
  → verify JWT → register in WsManager

Send message: { type:"message", peer_id, content }
  → save to DB
  → peer online  → deliver via WS
  → peer offline → Expo Push notification

Receive: { type:"message" } or { type:"ack", message_id }
```

---

## 7. Development Phases

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Backend: auth, profiles, discover, photos, admin | ✅ Done |
| 2 | Backend: messaging REST + WebSocket + push | ✅ Done |
| 3 | Mobile: all screens + push notifications | ✅ Done |
| 4 | Admin dashboard | ✅ Done |
| 5 | Integration + E2E testing (40/40 backend tests) | ✅ Done |
| 6 | Production cutover + app stores | ✅ Done |

---

## 8. Folder Structure

```
APP/
├── MASTER_PLAN.md
├── backend/   — BACKEND_PLAN.md + Express project
├── admin/     — ADMIN_PLAN.md  + React/Vite project
└── mobile/    — MOBILE_PLAN.md + Expo project
```

---

## 9. Transition Strategy

| Step | When | Action |
|------|------|--------|
| Build | Phase 1–4 | New stack in `APP/`; Flet app untouched |
| Test | Phase 5 | Both stacks against same SQLite file |
| Cutover | Phase 6 | Deploy backend; release mobile app |
| Retire | Post-6 | Delete `src/` (Flet app) ✅ Done |

---

## 10. Remaining Missions

### Mission 1 — Infrastructure & Server
> Set up the production server before anything else can go live.

- [ ] Choose a cloud provider (VPS, Render, Railway, Fly.io, AWS EC2, etc.)
- [ ] Provision a server with Docker installed
- [ ] Register a domain (e.g. `yahdav.app`) and point DNS:
  - `api.yahdav.app` → backend server IP
  - `admin.yahdav.app` → same server or CDN
- [ ] Obtain SSL/TLS certificate (Let's Encrypt / Certbot) for both subdomains
- [ ] Configure nginx reverse-proxy on the server:
  - `api.yahdav.app` → `localhost:3000` (backend)
  - `admin.yahdav.app` → `localhost:5173` (admin dashboard)

---

### Mission 2 — Backend Deployment
> Install Node.js on the server and run the backend as a PM2 process.

- [ ] Install Node.js 20+ on the server (via NodeSource or nvm)
- [ ] Install PM2 globally: `npm install -g pm2`
- [ ] Copy the `APP/backend/` source to the server
- [ ] Create `APP/backend/.env` on the server (never committed — fill from `.env.example`)
- [ ] Generate a strong `JWT_SECRET`: `node -e "console.log(require('crypto').randomBytes(48).toString('hex'))"`
- [ ] Set `ADMIN_CORS_ORIGIN` to the deployed admin URL (e.g. `https://admin.yahdav.app`)
- [ ] Set `DB_PATH` to an absolute path on a persistent directory (e.g. `/var/data/yahdav.sqlite3`)
- [ ] Set `UPLOADS_DIR` to an absolute path on a persistent directory (e.g. `/var/data/uploads`)
- [ ] Build: `npm install && npm run build` inside `APP/backend/`
- [ ] Start with PM2: `pm2 start dist/server.js --name yahdav-backend`
- [ ] Persist across reboots: `pm2 startup` (run the printed command), then `pm2 save`
- [ ] Verify: `GET https://api.yahdav.app/health` returns `{ ok: true }`

---

### Mission 3 — Admin Dashboard Deployment
> Build the static dashboard and serve it with nginx installed directly on the server.

- [ ] Set `VITE_API_BASE_URL=https://api.yahdav.app` in `APP/admin/.env.local`
- [ ] Build the dashboard: `npm run build` in `APP/admin/`
- [ ] Copy `admin/dist/` to the server web root (e.g. `/var/www/admin/`)
- [ ] Copy `APP/admin/nginx.conf` into `/etc/nginx/sites-available/admin` and update the `root` path to match the web root above
- [ ] Enable the site: `ln -s /etc/nginx/sites-available/admin /etc/nginx/sites-enabled/admin`
- [ ] Reload nginx: `nginx -t && systemctl reload nginx`
- [ ] Open `https://admin.yahdav.app/login` and verify the login page loads

---

### Mission 4 — First Admin Account
> Create the first admin user so the dashboard is usable.

- [ ] On the production backend, call `POST /auth/signup` to create your account
- [ ] Run the following against the production SQLite database:
  ```sql
  UPDATE auth_credentials SET is_admin = 1 WHERE username = 'your-username';
  ```
- [ ] Log in to `https://admin.yahdav.app` and verify admin access

---

### Mission 5 — Expo & EAS Setup
> Link the mobile app to an Expo account before building for stores.

- [ ] Create an account at [expo.dev](https://expo.dev) if not already done
- [ ] Run `eas init` inside `APP/mobile/` — this generates a real `projectId`
- [ ] Replace `REPLACE_WITH_EAS_PROJECT_ID` in `app.json` with the generated ID
- [ ] Replace `REPLACE_WITH_EXPO_ACCOUNT_USERNAME` in `app.json` with your Expo username
- [ ] Verify `eas.json` production env has `EXPO_PUBLIC_API_BASE_URL=https://api.yahdav.app`

---

### Mission 6 — iOS App Store
> Prepare and submit the iOS build.

- [ ] Enroll in the Apple Developer Program ($99/year) at [developer.apple.com](https://developer.apple.com)
- [ ] Create an App Store Connect record for יחדיו (bundle ID: `com.yahdav.app`)
- [ ] Fill in `eas.json` → `submit.production.ios`:
  - `appleId` — your Apple ID email
  - `ascAppId` — App Store Connect numeric app ID
  - `appleTeamId` — your team ID (found in Apple Developer account)
- [ ] Build: `eas build --platform ios --profile production`
- [ ] Submit: `eas submit --platform ios --profile production`
- [ ] In App Store Connect: add screenshots (required sizes), Hebrew description, age rating, privacy policy URL
- [ ] Submit for Apple review

---

### Mission 7 — Android Play Store
> Prepare and submit the Android build.

- [ ] Create a Google Play Console account ($25 one-time) at [play.google.com/console](https://play.google.com/console)
- [ ] Create a new app record for יחדיו (package: `com.yahdav.app`)
- [ ] Create a service account in Google Cloud Console, grant Play Console access, download JSON key
- [ ] Place the JSON key at `APP/mobile/google-play-service-account.json` (never committed)
- [ ] Build: `eas build --platform android --profile production`
- [ ] Submit: `eas submit --platform android --profile production`
- [ ] In Play Console: add screenshots, Hebrew store listing, content rating questionnaire
- [ ] Roll out to internal track → closed testing → production

---

### Mission 8 — Device Testing
> Verify real-device behaviour before public release.

- [ ] RTL layout — open every screen on a Hebrew-locale Android and iOS device, confirm visual alignment
- [ ] Push notifications — send a message while the recipient app is in background; confirm notification arrives
- [ ] WebSocket reconnect — kill network mid-chat, restore it; confirm messages resume
- [ ] Deep link — tap a push notification; confirm it opens the correct `ChatScreen`
- [ ] Photo upload — pick from gallery and camera on both platforms; confirm upload + display
- [ ] Auto-login — force-close the app, reopen; confirm session restores without login screen

---

### Mission 9 — Database Backup Strategy
> Protect user data on the production server.

- [ ] Schedule a daily backup of `data/yahdav.sqlite3` (cron + `cp` or `sqlite3 .backup`)
- [ ] Store backups off-server (S3, Backblaze, or similar)
- [ ] Test restore procedure at least once before going live

---

### Mission 10 — Monitoring & Observability
> Know when something breaks before users report it.

- [ ] Set up uptime monitoring for `https://api.yahdav.app/health` (UptimeRobot, BetterUptime, etc.)
- [ ] Configure alerts (email or SMS) when the health check fails
- [ ] Review backend logs on first week of production: `docker compose logs -f backend`
