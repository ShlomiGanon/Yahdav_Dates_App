# יחדיו (Yahdav)

A Hebrew-language, RTL-first Jewish dating app: a Node.js/Express
backend, a React web app, a React Native (Expo) mobile app, a React
admin dashboard, and a shared TypeScript package tying business logic
together across all three clients.

For how the system is designed and why, see
**[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)**. For open and
planned work, see **[`docs/BACKLOG.md`](./docs/BACKLOG.md)**.

## Status

Backend, web, mobile, and admin are all feature-complete — every page
the shared page registry declares is routed and fully built, at feature
parity across web and mobile except where a documented, deliberate UX
difference applies (see `docs/ARCHITECTURE.md` §7.4). What remains is
almost entirely operational: there is no live server deployment yet, and
mobile has no signed/store-submitted build yet. See
[`docs/BACKLOG.md`](./docs/BACKLOG.md) for the full, current list.

## Repository layout

```
APP/
├── backend/    Node.js/Express API + WebSocket server (the single source of truth)
├── web/        React web app for end-users
├── mobile/     React Native (Expo) app for iOS/Android end-users
├── admin/      React admin dashboard
├── shared/     Pure-TypeScript logic shared across the clients
└── tests/      All test suites, one folder per package

docs/
├── ARCHITECTURE.md   System design, conventions, CI/CD — start here
└── BACKLOG.md        Open and planned work

.github/workflows/
├── test.yml           Runs all four packages' test suites
├── build-shared.yml   Reusable: builds web + admin + the backend server package
├── release.yml        Production release, triggered by publishing a GitHub Release
└── release-dev.yml     Manual dev build (runtime-configurable mobile API URL)
```

## Running locally

Each app needs the backend running first.

### 1 — Backend

```
cd APP/backend
npm install
cp .env.example .env     # fill in JWT_SECRET at minimum
npm run dev              # http://localhost:3000
```

### 2 — Web app

```
cd APP/web
npm install
npm run dev               # http://localhost:5174
```

### 3 — Admin dashboard

```
cd APP/admin
npm install
cp .env.example .env.local   # VITE_API_BASE_URL=http://localhost:3000
npm run dev                   # http://localhost:5173, needs an is_admin=1 account
```

### 4 — Mobile app

```
cd APP/mobile
npm install
npx expo start    # scan the QR code with Expo Go
```

Expo Go on a physical device can't reach `localhost` — set
`EXPO_PUBLIC_API_BASE_URL` to your machine's local network IP (see
`docs/ARCHITECTURE.md` §11 for where).

### Running the tests

```
cd APP/backend && npm test
cd APP/shared  && npm test
cd APP/web     && npm test
cd APP/mobile  && npm test
cd APP/admin   && npm test
```

## Creating a release

**Production:** publish a GitHub Release. `release.yml` picks it up
automatically, verifies the tagged commit has a passing `Tests` run,
builds the backend/web/admin into a `yahdav-server-<tag>.zip`, builds an
Android APK, and attaches both to the Release. See
`APP/backend/docs/LOCAL_SETUP.md` for what to do with the resulting ZIP,
and `REMOTE_SETUP.md` for deploying it to a real server.

**Dev build:** run `release-dev.yml` manually (Actions tab →
"Release (Dev)" → Run workflow). Same server/web/admin build; the
Android build instead produces a distinctly-branded dev APK
(`com.yahdav.app.dev`) whose API server address is entered at runtime
by whoever installs it, not baked in. Both artifacts publish to a
rolling `dev-latest` pre-release, replacing the previous run's assets.

Neither workflow deploys anywhere automatically — both only build and
package. See `docs/ARCHITECTURE.md` §10 for the full pipeline design.
