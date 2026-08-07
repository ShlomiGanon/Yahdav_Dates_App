# Local Setup — Running a Release Package

This guide covers running a packaged release (`yahdav-server-<version>.zip`,
built by `.github/workflows/release.yml`) on your own machine. It does not
cover running the backend from source for development — see the root
`README.md` "Running locally" section for that.

For deploying this same package to a real remote server instead, see
`REMOTE_SETUP.md` in this folder.

---

## What's in the package

```
yahdav-server-<version>/
├── dist/                 ← compiled backend (run this, not src/)
├── migrations/           ← versioned SQL, applied automatically on startup
├── public/
│   ├── web/               ← built customer-facing web app (served at /)
│   └── admin/              ← built admin dashboard (served at /admin)
├── docs/
│   ├── LOCAL_SETUP.md      ← this file
│   └── REMOTE_SETUP.md
├── package.json
├── package-lock.json
└── .env.example
```

Deliberately **not** included: `node_modules/` (install it yourself — see
below), any real `.env`, and any database file or uploaded photos. You're
always starting from a clean slate.

## 1 — Prerequisites

- **Node.js 22** (matches what CI builds and tests against — see
  `docs/ARCHITECTURE.md`'s Technology Stack table at the project root).

## 2 — Extract and install dependencies

```
unzip yahdav-server-<version>.zip
cd yahdav-server-<version>
npm install --omit=dev
```

`--omit=dev` skips devDependencies (TypeScript, test tooling, …) — nothing
in `dist/` needs them to run.

## 3 — Configure environment variables

```
cp .env.example .env
```

Then edit `.env`:

| Variable | Required? | What to do |
|----------|-----------|------------|
| `JWT_SECRET` | **Yes** | Generate one: `node -e "console.log(require('crypto').randomBytes(48).toString('hex'))"` and paste the output in. Never reuse the placeholder value. |
| `PORT` | No | Defaults to `3000`. |
| `DB_PATH` | No | Defaults to `data/yahdav.sqlite3`, created automatically on first start. |
| `UPLOADS_DIR` | No | Defaults to `data/uploads`, created automatically. |
| `WEB_PUBLIC_DIR` / `ADMIN_PUBLIC_DIR` | No | Already correct for this package's layout (`public/web`, `public/admin`) — only change these if you moved the `public/` folder. |
| `ADMIN_CORS_ORIGIN` | No | Not needed for this setup — web and admin are served by this same server, same origin. Only relevant if you host either frontend somewhere else instead. |
| `DOMAIN` | No | Not used locally at all — see `REMOTE_SETUP.md`. |
| `EXPO_PUSH_URL` | No | Leave as the default unless you have a reason to change it. |

## 4 — Start the server

```
node dist/server.js
```

No process manager (PM2, systemd, …) is used for local runs — that's a
remote-deployment concern, covered in `REMOTE_SETUP.md`. If you want the
server to keep running after you close the terminal, run it in a separate
window/tab, or use your OS's own tools for that.

On first start, migrations apply automatically — you'll see
`[migrate] applied 001_initial.sql` in the log.

## 5 — Verify it's running

```
curl http://localhost:3000/api/health
```

Expect `{"ok":true}`.

Then, in a browser:

- **Web app** — `http://localhost:3000/`
- **Admin dashboard** — `http://localhost:3000/admin`

## 6 — Create the first admin account

There's no bootstrap script for this yet (tracked in `docs/BACKLOG.md`
at the project root). Sign up a normal account first — through the web
app, or directly:

```
curl -X POST http://localhost:3000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","username":"admin","password":"choose-a-real-password"}'
```

Then flip `is_admin` on that row directly in the SQLite file (stop the
server first to avoid a concurrent-write conflict):

```
node -e "const { DatabaseSync } = require('node:sqlite'); const db = new DatabaseSync('data/yahdav.sqlite3'); db.exec(\"UPDATE auth_credentials SET is_admin = 1 WHERE email = 'you@example.com'\"); db.close();"
```

Restart the server and log into `/admin` with that account.

## Rebuilding the package yourself

You shouldn't normally need to — `release.yml` does this on every GitHub
Release. If you want to reproduce the package locally from source instead
of downloading a release asset, see the root `README.md`'s "Running
locally" section for how to build each of `backend`, `web`, and `admin`
individually, then copy `web/dist/` → `public/web/` and `admin/dist/` →
`public/admin/` under the backend's own folder before starting it.
