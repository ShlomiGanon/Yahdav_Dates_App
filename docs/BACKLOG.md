# Backlog — יחדיו (Yahdav)

Open, known, tracked work — not a wishlist, a record of what's actually
been identified as pending. Each item states what needs doing, why it
matters, and a rough scope (small / medium / large). See
[`ARCHITECTURE.md`](./ARCHITECTURE.md) for how the system is built today.

---

## Deployment & Infrastructure

### Provision a real server, domain, and SSL
**What:** Stand up a Linux server, register a domain, point DNS at it,
issue an SSL certificate.
**Why:** The product currently only runs locally — there is no live
deployment anywhere. Everything else in this section depends on this
existing first.
**Scope:** Medium. Fully documented, step by step, in
`APP/backend/docs/REMOTE_SETUP.md` — this is "follow the guide and pay
for a server," not open design work.

### Deploy the backend under a process manager
**What:** Install Node.js 22 + PM2 on the server, run the backend under
it (auto-restart on crash, start on boot).
**Why:** Local runs use plain `node dist/server.js`; that's not
sufficient for something meant to stay up unattended.
**Scope:** Small, once the server exists. Documented in
`REMOTE_SETUP.md`.

### nginx reverse proxy + WebSocket passthrough
**What:** Configure nginx to proxy `443` → the backend's internal port,
with the `Upgrade`/`Connection` headers the chat WebSocket needs.
**Why:** The backend shouldn't bind a public/privileged port directly;
nginx also fronts SSL termination.
**Scope:** Small. Documented in `REMOTE_SETUP.md`, including the exact
config block needed.

### Bootstrap the first admin account
**What:** No seed/bootstrap script exists — the first `is_admin = 1`
account has to be created by hand, directly in the SQLite file (a
documented one-liner in `LOCAL_SETUP.md`/`REMOTE_SETUP.md`).
**Why:** There's currently no other way to get an admin account at all
on a fresh deployment.
**Scope:** Small to build a real script; trivial (but manual, every
time) to keep doing it the current way.

### Backups
**What:** Daily `sqlite3 .backup` of the database file plus a periodic
sync of `data/uploads/`, shipped off-server (S3, another host via
rsync/scp — not decided).
**Why:** Nothing is backed up today. A single-file SQLite database with
no backup is a real data-loss risk once real users exist.
**Scope:** Small. The exact commands are already documented in
`REMOTE_SETUP.md`; what's missing is actually scheduling and verifying
them against a real off-server target.

### Monitoring
**What:** An uptime checker (paid service, or a cron job hitting
`/api/health`) with alerting.
**Why:** Nothing currently notices if the server goes down.
**Scope:** Small.

### Fix the backend's missing workspace-symlink install step in CI
**What:** `test.yml`'s `backend` job runs a second `npm ci` at the
workspace root (`working-directory: APP`) specifically to create the
`@yahdav/shared` npm-workspace symlink that a plain `npm ci` inside
`APP/backend` alone doesn't produce. Neither `release.yml`'s nor
`release-dev.yml`'s `build-server` job does this.
**Why:** It hasn't caused an observed failure yet, because `tsc`
apparently doesn't need the real symlink to type-check against
`shared`'s `.d.ts` output — only an actual `require()` at runtime would.
Since CI only builds and packages the backend (never runs it), this gap
is latent, not active. It's still a real, first-hand-confirmed
inconsistency between two CI paths that both need to resolve
`@yahdav/shared`, and worth closing before it causes a confusing failure
somewhere less obvious.
**Scope:** Small — add one more `npm ci` step, matching `test.yml`'s
existing pattern.

---

## Mobile & App Store

### Initialize EAS
**What:** Run `eas init` in `APP/mobile/`, filling in a real Expo
project ID. `mobile/app.config.js`'s `extra.eas.projectId` and `owner`
are still the literal placeholders `REPLACE_WITH_EAS_PROJECT_ID` /
`REPLACE_WITH_EXPO_ACCOUNT_USERNAME`.
**Why:** Blocks any EAS-based build or submission path (see the iOS item
below, which depends on this if EAS is the chosen path).
**Scope:** Small — an account/setup task, not a code change.

### Android release signing
**What:** `release.yml`/`release-dev.yml`'s `build-android`/
`build-android-dev` jobs currently produce an **unsigned** APK
(`app-release-unsigned.apk`), which Android refuses to install as-is.
To fix: generate a release keystore, store it (base64-encoded) plus its
passwords as GitHub Secrets (e.g. `ANDROID_KEYSTORE_BASE64`,
`ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`),
decode it to a file before the Gradle build step, and point
`android/app/build.gradle`'s `signingConfigs.release` at it (Expo's
`expo prebuild` output already scaffolds this block, commented out).
**Why:** Without this, nobody outside the CI runner can actually install
the built Android APK.
**Scope:** Medium — mostly credential/secrets setup, plus wiring the
Gradle config; the workflow's "locate the APK" step already
auto-adapts to a signed output filename with no further change needed.

### iOS build
**What:** Not implemented — `build-ios` in `release.yml` is a disabled
(`if: false`) placeholder job, already wired into the dependency graph.
Two real paths, not yet chosen:
- **(a) EAS Build** (`eas build --platform ios`) — needs an
  `EXPO_TOKEN` secret, EAS actually initialized (see above), and Apple
  credentials registered with EAS (`eas credentials`). EAS build
  artifacts land on Expo's own servers, not in the runner — a follow-up
  step would need to download the finished `.ipa` (`eas build:download`
  or the REST API) before it could be attached to a Release the way
  `build-server`/`build-android` do it.
- **(b) A macOS runner** (`runs-on: macos-latest` — meaningfully more
  expensive than `ubuntu-latest`) running `expo prebuild --platform ios`
  + `xcodebuild` directly, with the signing certificate/provisioning
  profile supplied as base64-encoded GitHub Secrets (same pattern as
  Android's keystore, above).
Either way, an enrolled Apple Developer Program account ($99/yr) with a
distribution certificate and provisioning profile is a prerequisite.
**Why:** There is currently no iOS build at all, signed or unsigned.
**Scope:** Large — real money (Apple Developer Program), a genuine
architecture choice between (a) and (b), and non-trivial CI work either
way.

### Google Play submission
**What:** Create a Google Play developer account, build a signed
release (depends on the Android signing item above), submit for review.
**Why:** No path to the Play Store exists yet.
**Scope:** Large — account setup, store listing content, review process.

### Device testing pass
**What:** A real pass on physical devices covering RTL rendering, push
notifications, WebSocket reconnect behavior, and deep links.
**Why:** All of this has been built and unit/integration-tested, but
never verified end-to-end on real hardware.
**Scope:** Medium.

### Standardize Allman brace style across the mobile codebase
**What:** Most of `mobile/src` still uses K&R-style braces (`{` on the
same line), despite `ARCHITECTURE.md` listing Allman as a project-wide
leading principle. New mobile code written since this was flagged (the
runtime-URL gate, the ack-reconciliation fix) is Allman; the rest of the
codebase was never swept.
**Why:** Inconsistency between the stated convention and most of the
actual mobile source.
**Scope:** Medium — mechanical, but touches most files under
`mobile/src`; best done as its own dedicated pass, not mixed into
unrelated changes.

---

## Security & Hardening

### Rate limiting
**What:** No rate limiting exists anywhere in the backend — most
importantly on `/api/auth/*`, which has no brute-force protection at
all.
**Why:** A production auth endpoint without rate limiting is a real,
known exposure.
**Scope:** Small — a middleware package (e.g. `express-rate-limit`) and
a policy decision on limits, not a design problem.

### Security-headers middleware
**What:** No `helmet` (or equivalent) wired into `app.ts` — no
`Content-Security-Policy`, `X-Frame-Options`, etc.
**Why:** Standard baseline hardening that's currently entirely absent.
**Scope:** Small.

---

## Code Quality & Technical Debt

### `shared/config.ts` triggers a Vite deprecation warning
**What:** `web/vite.config.ts` imports `APP_NAME` from
`shared/config.ts` directly (for the `index.html` title-injection
plugin). Since `shared/package.json` has no `"type": "module"`, Vite's
native config loader logs: *"ESM syntax in a file loaded as CommonJS"*,
and warns this will become a hard error in a future Vite major version.
The web app builds and runs correctly today — this is a forward-looking
warning, not a current failure.
**Why:** The root cause (`shared/`'s implicit CommonJS module type,
despite using ESM `export` syntax throughout) is a foundational
property of the `shared` package. Fixing it properly (adding
`"type": "module"`) has a wide blast radius: it would affect every
consumer — the backend's real npm-dependency resolution of the compiled
`dist/`, mobile's Metro bundler resolution, and web's own bundler-alias
resolution — not just this one Vite config file. That's why it wasn't
fixed when discovered; it needs its own deliberate pass, not a
side-effect fix.
**Scope:** Medium — the fix itself is probably small, but verifying it
doesn't break any of the three very different consumption paths (raw
source import, compiled npm dependency, bundler alias) needs real
end-to-end testing of all three, not just a type check.

### Stale `APP/review.md` comment references across the codebase
**What:** Roughly 28 source and test files (mostly under `shared/`, plus
a few in `mobile/src/api/` and `tests/`) contain historical comments
referencing `APP/review.md finding X.X` — a file that no longer exists
as of this documentation consolidation (its durable content is now in
`ARCHITECTURE.md` §7 instead).
**Why:** These were left in place deliberately during the documentation
cleanup that produced this file — updating dozens of source-code
comments across the whole codebase is a materially different, much
larger task than consolidating scattered top-level docs, and doing it
as a side effect risked touching files well outside that task's actual
scope.
**Scope:** Medium — mechanical (grep + replace each reference with a
pointer into `ARCHITECTURE.md` §7, or simply remove the now-orphaned
citation), but touches ~28 files.

### Standardize Allman brace style across the mobile codebase
See the Mobile & App Store section above — listed there since it's
mobile-specific, but it's a code-quality item, not a product feature.

---

## Product Decisions

### Web photo resize
**What:** Mobile downsizes photos client-side before upload (1080px
longest edge, 0.8 JPEG quality, via `expo-image-manipulator`). Web
currently uploads the original file as-is, with no client-side resize
at all.
**Why:** This is a genuine product inconsistency, not a bug: web users
can currently upload full-resolution originals (slower uploads, more
storage, more backend-side risk) while mobile users cannot. Needs a
product decision on whether web should get an equivalent (e.g.
Canvas-based) resize before anyone builds it — if so, the *policy*
(1080px / 0.8 quality / JPEG) belongs in `shared/config.ts` even though
the two implementations (`expo-image-manipulator` vs. the Canvas API)
can't actually share code.
**Scope:** Small to medium, once decided — the implementation itself is
contained; the open part is entirely the decision, not the code.
