# Remote Setup — Deploying to a Real Server

**Status: not yet applicable.** As of this writing the product runs
locally only (see `LOCAL_SETUP.md`) — there is no provisioned server, no
registered domain, and no SSL certificate yet. This guide is written in
full anyway, ahead of actually needing it, so the steps exist the moment
they do become relevant. Every `your-domain.example.com`-shaped value
below is a placeholder to replace once a real domain exists.

This assumes a single Linux server (examples use Ubuntu/Debian + `apt`)
running the backend, which also serves the web app and admin dashboard —
the same one-server architecture as local, just reachable from the
internet instead of `localhost`.

---

## 1 — Provision the server

- A VM/server running Ubuntu LTS (or your distribution of choice) with a
  public IP address.
- **Node.js 22** installed (matches `docs/ARCHITECTURE.md`'s Technology
  Stack table at the project root — install via
  [NodeSource](https://github.com/nodesource/distributions) or your
  distro's preferred method, not covered here since it varies).
- A registered domain, e.g. `your-domain.example.com`, with its DNS **A
  record pointed at the server's public IP**. Propagation can take a
  while — confirm with `dig your-domain.example.com` before continuing.

## 2 — Get the release package onto the server

Download the release asset directly from GitHub (replace `<version>`
with the actual release tag):

```
wget https://github.com/<owner>/<repo>/releases/download/<version>/yahdav-server-<version>.zip
unzip yahdav-server-<version>.zip
cd yahdav-server-<version>
npm install --omit=dev
```

## 3 — Configure environment variables

```
cp .env.example .env
```

Same variables as `LOCAL_SETUP.md`, with these differences for a remote
deployment:

| Variable | What to set |
|----------|-------------|
| `JWT_SECRET` | **Yes, required, and must be a real secret** — generate with `node -e "console.log(require('crypto').randomBytes(48).toString('hex'))"`. Never reuse a value that was ever used locally or committed anywhere. |
| `DOMAIN` | `your-domain.example.com` — informational (see `.env.example`'s comment); used below when writing the nginx config and requesting the SSL certificate. Not read by the app itself. |
| `ADMIN_CORS_ORIGIN` | Leave as default. This server serves web and admin same-origin (same as local), so cross-origin isn't in play unless you deliberately host one of them elsewhere instead. |
| `PORT` | Leave at `3000` (default) — nginx proxies the public-facing `443` to this internal port; there's no reason for Node to bind a privileged port directly. |

## 4 — Run the server under a process manager

Local runs use plain `node dist/server.js`; a remote server needs
something to keep it running, restart it on crash, and start it on boot.
[PM2](https://pm2.keymetrics.io/) is the straightforward option:

```
npm install -g pm2
pm2 start dist/server.js --name yahdav-server
pm2 save
pm2 startup     # prints a command to run once, to survive a server reboot
```

Useful commands going forward: `pm2 logs yahdav-server`, `pm2 restart
yahdav-server`, `pm2 status`.

## 5 — nginx reverse proxy

Install nginx (`apt install nginx`), then create
`/etc/nginx/sites-available/yahdav`:

```nginx
server {
    listen 80;
    server_name your-domain.example.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The `Upgrade`/`Connection` headers matter here — the chat WebSocket
(`/ws`) needs them to establish through the proxy, not just plain HTTP
routes.

```
ln -s /etc/nginx/sites-available/yahdav /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

## 6 — SSL via Let's Encrypt

```
apt install certbot python3-certbot-nginx
certbot --nginx -d your-domain.example.com
```

Certbot rewrites the nginx config to redirect `80` → `443` and add the
certificate automatically; it also sets up auto-renewal. Confirm renewal
works ahead of time with `certbot renew --dry-run`.

## 7 — Verify

```
curl https://your-domain.example.com/api/health
```

Expect `{"ok":true}`. Then check `https://your-domain.example.com/` (web)
and `https://your-domain.example.com/admin` (admin) in a browser.

## 8 — First admin account

Same procedure as `LOCAL_SETUP.md` step 6 — sign up a normal account,
then flip `is_admin` directly in the SQLite file on the server (stop the
server first):

```
node -e "const { DatabaseSync } = require('node:sqlite'); const db = new DatabaseSync('data/yahdav.sqlite3'); db.exec(\"UPDATE auth_credentials SET is_admin = 1 WHERE email = 'you@example.com'\"); db.close();"
pm2 restart yahdav-server
```

## 9 — Backups

The whole database is one WAL-mode SQLite file
(`data/yahdav.sqlite3`) — a raw file copy while the server is running can
catch it mid-write. Use SQLite's own online backup command instead, and
ship the result off-server (the example below just writes locally —
adjust the last line to your actual off-server target: S3, another host
via `rsync`/`scp`, etc.):

```
sqlite3 data/yahdav.sqlite3 ".backup '/var/backups/yahdav/yahdav-$(date +%F).sqlite3'"
```

Add that as a daily cron job (`crontab -e`):

```
0 3 * * * sqlite3 /path/to/data/yahdav.sqlite3 ".backup '/var/backups/yahdav/yahdav-$(date +\%F).sqlite3'"
```

Back up `data/uploads/` (the photo files) the same way, on the same
schedule — a plain `rsync`/`tar` is fine for that directory since it's
just static files, no in-flight-write concern like the database has.

## 10 — Monitoring

Nothing is set up yet. At minimum, point an uptime checker (a paid
service like UptimeRobot/Pingdom, or a simple cron job that `curl`s
`/api/health` and alerts on failure) at
`https://your-domain.example.com/api/health` so a crash or server outage
doesn't go unnoticed.

## Deploying a new release

```
pm2 stop yahdav-server
# extract the new release zip over the old one, but do NOT overwrite:
#   .env, data/, node_modules/
cd yahdav-server-<new-version>
npm install --omit=dev
pm2 restart yahdav-server
```

Migrations apply automatically on the next start — no manual DB step
needed for ordinary schema changes.
