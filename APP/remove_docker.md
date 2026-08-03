# Remove Docker — Plan & Record

## What was removed

| File | Reason |
|------|--------|
| `APP/backend/Dockerfile` | Multi-stage build — no longer needed |
| `APP/backend/.dockerignore` | Build-context exclusion file — no longer needed |
| `APP/docker-compose.yml` | Orchestrator for backend + admin nginx — no longer needed |

---

## How the backend runs without Docker

The backend is a plain Node.js / Express process. No container required.

### One-time setup on the server

```
# Install Node.js 20+ (e.g. via NodeSource or nvm)
# Then, in APP/backend/:

npm install          # install all dependencies
npm run build        # compile TypeScript → dist/
```

Copy `.env.example` to `.env` and fill in the production values (see MASTER_PLAN.md Mission 2).

### Start the server

**Simple (foreground):**
```
node dist/server.js
```

**Production (background, auto-restart):**

Install PM2 once:
```
npm install -g pm2
```

Start and persist:
```
pm2 start dist/server.js --name yahdav-backend
pm2 startup          # prints a command — run it once to register PM2 as a systemd service
pm2 save             # persist the process list across reboots
```

Useful PM2 commands:
```
pm2 logs yahdav-backend    # tail logs
pm2 restart yahdav-backend
pm2 stop yahdav-backend
pm2 status
```

---

## How the admin dashboard runs without Docker

The admin is a Vite-built static site. Serve it with nginx installed directly on the server.

### Build

```
# In APP/admin/:
npm run build        # produces admin/dist/
```

### nginx config

The file `APP/admin/nginx.conf` contains the ready-to-use nginx server block (SPA fallback + asset caching). Copy it into the server's nginx sites:

```
# copy dist/ to web root
cp -r admin/dist/ /var/www/admin/

# copy nginx config
cp admin/nginx.conf /etc/nginx/sites-available/admin
ln -s /etc/nginx/sites-available/admin /etc/nginx/sites-enabled/admin

# update the root path inside the config to: /var/www/admin
nginx -t && systemctl reload nginx
```

---

## Changes made to MASTER_PLAN.md

Mission 2 (Backend Deployment) and Mission 3 (Admin Dashboard Deployment) were rewritten to use PM2 + direct nginx instead of Docker.

---

## Verification checklist

- [ ] `APP/backend/Dockerfile` deleted
- [ ] `APP/backend/.dockerignore` deleted
- [ ] `APP/docker-compose.yml` deleted
- [ ] `GET http://localhost:3000/health` returns `{ ok: true }` when backend runs via `node dist/server.js`
- [ ] Admin `dist/` served correctly by nginx SPA config
