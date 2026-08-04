# Code Improvement Notes

Findings from a read-only review of `backend`, `mobile`, `web`, `admin`, and `shared`. Grouped by area, then by severity. File paths are relative to `APP/`.

---

## Cross-cutting (affects multiple apps)

### High
- **`shared` is architecturally unreachable for 3 of 4 consumers.** There's no root workspace `package.json`/`workspaces` config and no path alias except in `web` (`web/vite.config.ts:16-19`, `web/tsconfig.app.json:30-31`). `backend`, `admin`, and `mobile` have zero references to `@shared` and each reimplement equivalent logic locally instead. Fix: turn this into a real npm/pnpm workspace, or at least add the same `@shared` alias to admin/mobile/backend tsconfig + bundler config.
- **`shared`'s types have already drifted from the real backend contract**, which is worse than no shared types because it gives false confidence:
  - `shared/types/chat.ts:1-19` `Message`/`Conversation` don't match `backend/src/models/MessageModel.ts:4-20` (missing `AUDIO` msg_type, wrong field names for conversations, phantom `is_read`/`peer_photo` fields).
  - `shared/types/user.ts:3-16` `Profile`/`PeerProfile` use `photo_urls: string[]` while backend (`backend/src/models/ProfileModel.ts:4-13`) and mobile actually use a singular `photo_url` + separate photos list.
  - `is_admin` is typed inconsistently: `number` in `shared/types/auth.ts:200` and `admin/src/types.ts:1-6`'s hand-rolled type says `boolean`; `mobile/src/auth/AuthContext.tsx:7-12` also redeclares its own `User` type instead of importing `AuthUser`.
  - Fix order: correct the shared types against the actual backend response shape *before* wiring more consumers into `shared`, or they'll inherit compile-time-correct-but-runtime-wrong data.
- **Auth/API-client plumbing is duplicated 2-3x instead of shared:**
  - Axios instance + Bearer interceptor + 401-refresh-with-queueing: `mobile/src/api/axios.ts:1-61` vs `web/src/api/client.ts:1-87` vs `admin/src/api/axios.ts` — hand-written three times with cosmetic differences (e.g. web queues concurrent 401s, admin doesn't).
  - Auth controller (bootstrap-refresh, login, logout): `admin/src/auth/AuthContext.tsx` vs `web/src/auth/AuthContext.tsx`, near-verbatim.
  - Chat/Users API wrappers: `mobile/src/api/chat.ts`, `mobile/src/api/users.ts` reimplement `shared/api/chat.ts`'s `createChatApi`/`createUsersApi` almost line-for-line.
  - Fix: extract a platform-agnostic `createApiClient(baseURL, tokenStorage, onAuthFailure)` and `createAuthController(...)` into `shared`, parameterized by an injectable token-storage adapter, and have all three apps consume it.
- **WebSocket message frames bypass the validation the REST endpoint enforces.** `backend/src/websocket/wsServer.ts:38-78` accepts any `content`/`msg_type` with no length cap or allowlist, while `backend/src/routes/chat.routes.ts:41-45` enforces `isLength({max:4000})` and `isIn(['TEXT','AUDIO','IMAGE'])`. Combine with mobile's `useMessages.ts:85-92`, which pushes any WS payload with a `sender_id` straight into chat state without checking a message-type discriminator — a non-chat WS frame (typing indicator, presence ping) would render as a bogus chat bubble. Fix: share validation rules between the two entry points and add an explicit `event`/`type` check before mutating client-side chat state.

### Medium
- **`formatDate` logic duplicated three ways**: `mobile/src/utils/formatDate.ts:1-21` (has a NaN guard that `shared/utils/formatDate.ts:1-35` lacks), plus `admin/src/sections/users/{UserDetailPage,UserListPage}.tsx` hand-roll their own `date-fns` long-date formatting. Fix: consolidate into `shared/utils/formatDate.ts` (keep the NaN guard), add a `formatLongDate` export, and use it everywhere.
- **No error boundary anywhere** — grep for `ErrorBoundary`/`componentDidCatch` across mobile, web, and admin returns nothing. An uncaught render error blanks the whole screen with no fallback, despite each app otherwise investing in graceful loading/error states. Fix: add a top-level `ErrorBoundary` in each app's entry point.
- **Sequential (not combined) auth round-trips.** Both `admin/src/auth/AuthContext.tsx` and `web/src/auth/AuthContext.tsx` do `POST /auth/refresh` (or `/login`) then a separate `GET /auth/me` serially, doubling latency on every cold load and login. Admin's login response already inlines the user fields (`admin/src/api/auth.ts:4-11`) so this is half-solved there but not reused; web still does the extra round trip.
- **No runtime validation at API boundaries anywhere** (no zod/io-ts). All types are trust-the-server TS interfaces, which is exactly why the chat/profile type drift above went unnoticed. Fix: consider a lightweight shared zod schema used by both backend response serialization and client parsing.

---

## Backend (`backend/`)

### High
1. **Token type confusion — refresh tokens work as access tokens.** `src/middleware/authenticate.ts:16` and `src/models/SessionModel.ts:50-52` only run `jwt.verify()` and never check a `type` claim, even though `BACKEND_PLAN.md:242` documents `type:"access"`. A stolen/logged 30-day refresh token can be sent as a Bearer token and authenticate on any non-admin route. Fix: embed and verify a `type` claim on both token kinds.
2. **No rate limiting on `/auth/signup`, `/auth/login`, `/auth/refresh`** (`src/routes/auth.routes.ts`, `src/app.ts`) — wide open to credential stuffing. Fix: add per-IP/per-identifier rate limiting.
3. **Unhandled synchronous exceptions in the WS handler can crash the process.** `src/websocket/wsServer.ts:51-78` calls `MessageModel.send()` with no try/catch; a self-message or message to a nonexistent user throws on the `direct_messages` CHECK/FK constraint inside a raw `ws.on('message', ...)` callback — uncaught, with no process-level handler anywhere. This is a real DoS vector. Fix: wrap in try/catch, emit a `{type:"error"}` frame.
4. **Migration version tracking is broken for multi-file runs.** `src/database/migrate.ts:16-43` captures `row` once before the loop and never reassigns it, so every pending migration after the first does `INSERT` instead of `UPDATE` into `schema_version` (no PK), producing duplicate rows and unpredictable version reads. Masked today because only `001_initial.sql` exists — will break the moment a `002_*.sql` is added. Fix: track current version in a mutable variable, or `INSERT OR REPLACE` a single fixed row.
5. **Known-vulnerable transitive deps** (`npm audit`: 1 critical, 1 high, 1 moderate) — `bcrypt@5.1.1 → @mapbox/node-pre-gyp → tar@6.2.1` (path traversal, CVSS up to 8.2) and `uuid@10.0.0` (buffer bounds bug, fix needs a breaking v14 bump). Fix: `npm audit fix` / bump bcrypt's install path, plan a uuid v14 migration.
6. **Empty `PUT /users/me` body produces malformed SQL.** `src/database/queries/profile.queries.ts:51-57` builds `SET ${sets}, updated_at = ?` from `Object.keys(fields)` with no check that `fields` is non-empty; a body with only unrecognized keys produces `SET , updated_at = ?` → SQL syntax error surfaced as a generic 500. Fix: short-circuit with a 422/no-op when `fields` is empty.

### Medium
7. **Catch-all error handler discards all error context** (`src/middleware/errorHandler.ts:3-11`) — malformed JSON, DB constraint violations, and genuine bugs all collapse to `500 {error:"Internal server error"}`. Fix: branch on known error types before the fallback.
8. **N+1 queries + unbounded in-memory scan in admin user search.** `src/routes/admin.routes.ts:18-50` does one `authQueries.findById` per row, and the search path pulls up to 10,000 profile rows into memory then filters in JS instead of pushing the filter into SQL. Fix: index-backed `LIKE` query with a join, not a client-side scan.
9. **Self-message / nonexistent recipient only rejected by DB constraint, not validated.** `src/routes/chat.routes.ts:47-73` never checks `sub !== peerId` or recipient existence before calling `MessageModel.send`, unlike `profile.routes.ts:189`'s explicit check — produces a raw 500 instead of a clean 422/404 (same root cause as WS finding above).
10. **`ADMIN_CORS_ORIGIN` is configured but never applied.** `src/config.ts:20` and `.env.example` define it, but no `cors` package is installed and `src/app.ts` sets no CORS headers — a browser-based admin dashboard on a different origin would be blocked. Fix: add scoped `cors` middleware or remove the dead config.
11. **Ad hoc `require()` + inline SQL bypasses the query-ledger convention.** `src/models/ProfileModel.ts:110-119` (`getPeerProfile`) does `require('../database/connection')` and inlines raw SQL instead of adding a method to `profileQueries`, breaking the documented "zero inline SQL outside `database/queries/`" rule and mixing CommonJS into an otherwise ESM-style codebase.
12. **Zero test coverage for the WebSocket layer** — `tests/` covers admin/auth/chat/profile routes but nothing exercises `src/websocket/wsServer.ts` or `wsManager.ts`, including the crash risk in finding 3.
13. **`BACKEND_PLAN.md` is materially out of date** — still describes a Controllers layer that doesn't exist and a photo API contract (`file`+`slot`, `/photos/:slot_index`) that doesn't match the implemented one (`photo`, `/me/photos/:photo_id` by UUID). New contributors following the doc will build against the wrong contract.

### Low
14. `src/database/connection.ts:1` depends on the experimental `node:sqlite` (requires Node 25) with no `engines` field in `package.json` to guard incompatible installs.
15. Account enumeration on signup — `src/routes/auth.routes.ts:29-36` returns distinct `username_taken`/`email_taken` errors.
16. No structured logging — bare `console.log`/`console.error` throughout (`errorHandler.ts:9`, `pushService.ts:44,50`, `migrate.ts:38,42`), no levels/timestamps/correlation IDs.
17. Uploaded photos served via `express.static` (`src/app.ts:18`) with no access control — acceptable while filenames are UUIDs, but worth a deliberate comment since any URL leak grants permanent unauthenticated access.

---

## Mobile (`mobile/`)

### High
1. **Duplicated WebSocket reconnect logic.** `src/hooks/useMessages.ts:14-108` and `src/hooks/useConversations.ts:9-74` copy-paste ~60 lines of `connectWs`/backoff/cleanup. Fix: extract a shared `useReconnectingSocket(url, { onMessage, onOpen })` hook.
2. **`useAutoLogin.ts:18-31` treats network failure the same as an invalid session** — any error from `GET /auth/me`, including a plain timeout at cold boot, hits the same `catch { clearTokens() }` and force-logs-out the user, wiping a valid refresh token. Fix: distinguish `error.response` (401 → clear) from a network-layer failure (keep tokens, show a retry/offline state).
3. **WS message handler doesn't validate payload shape before mutating chat state** (see cross-cutting finding above) — `src/hooks/useMessages.ts:85-92`.
4. **`SignupScreen.tsx:7,50` calls `api.post('/auth/signup', ...)` directly**, violating the project's own documented convention (`MOBILE_PLAN.md` §8: "no screen calls `api.get/post` directly"). `AuthContext.tsx:31,40` does the same for login/logout. Fix: add `src/api/auth.ts` and route all auth calls through it.

### Medium
5. **`User` type defined twice**, identically, in `src/auth/AuthContext.tsx:7-12` and `src/auth/useAutoLogin.ts:5-10` — will silently drift since structural typing won't catch a partial edit. Fix: move to `src/types/user.ts` and import in both places.
6. **Documented `writingDirection: 'rtl'` convention never implemented.** `MOBILE_PLAN.md` §12 requires it on all `TextInput`; `HebrewInput.tsx:36-37` only sets `textAlign="right"`. Mostly self-corrects under `I18nManager.forceRTL(true)` but mixed Hebrew/Latin input can show wrong caret behavior.
7. **`api/axios.ts:26-60` refresh-failure path doesn't distinguish network errors from real auth rejection** — a transient network blip on `/auth/refresh` still triggers full logout via `onAuthFailure?.()`. Fix: only log out on 401/403, not on network-level failures.
8. **No error boundary around `ImageManipulator.manipulateAsync`** in `src/utils/resizePhoto.ts:10-14` (callers: `useMyProfile.ts:53`, `useMyPhotos.ts:38`) — a manipulation failure throws before `setUploading(true)` runs, producing an unhandled rejection with no user-facing error.
9. **`FormData` photo upload uses `as any`** at `useMyProfile.ts:55` and `useMyPhotos.ts:40`. Fix: define `type RNFile = { uri: string; name: string; type: string }` instead of `any`.
10. **Optimistic message IDs can collide.** `useMessages.ts:114`: `` `tmp-${Date.now()}` `` — two messages in the same millisecond get the same key, breaking `keyExtractor` and the replace/filter logic. Fix: append a random/counter suffix.

### Low
11. Unused imports: `View, Text` in `src/navigation/MainStack.tsx:2`; `Dimensions` in `src/screens/profile/MyProfileScreen.tsx:4`.
12. **`useConversations.ts:58` reloads the entire conversation list on every WS message** regardless of relevance — full `GET /chat/conversations` refetch per incoming message. Fix: incrementally update the affected conversation from the WS payload instead.
13. Client derives username from email locally (`SignupScreen.tsx:19-24`) with no real collision handling — a username collision from the backend surfaces as a misleading "email already exists" message.
14. Hardcoded fallback API base URL `src/api/axios.ts:4` (`?? 'http://localhost:3000'`) with no runtime assertion if the env var is missing in a real build.
15. No top-level `ErrorBoundary` around `RootNavigator` in `main.tsx` despite the app otherwise investing heavily in graceful degradation elsewhere.

**What's working well:** consistent use of typed API modules (`usersApi`/`chatApi`) except the auth exception above, design tokens used everywhere with no stray magic numbers, consistent loading/error/success shapes, strict TS with only 3 narrow/justified `any` usages, and a reasonable secure-token pattern (SecureStore for refresh, in-memory access token).

---

## Web (`web/`)

### High
1. **Login button is non-functional.** `src/pages/LoginPage.tsx:80-85` renders `<Button label="התחברות" onPress={() => {}} .../>`, and `Button` (`src/components/Button.tsx:27`) hardcodes `type="button"`. The only way to log in is pressing Enter inside a text field. Fix: give `Button` a `type` prop and pass `type="submit"`, or wire `onPress` to the submit handler.

### Medium
2. **All six pages beyond login are unwired stubs.** `DiscoverPage.tsx`, `ProfilePage.tsx`, `PeerProfilePage.tsx`, `ChatHistoryPage.tsx`, `ChatPage.tsx` render only static placeholder text and never call `usersApi`/`chatApi` from `src/api/client.ts`; `components/PhotoUpload.tsx` is fully built but imported nowhere. Worth flagging so it isn't mistaken for feature-complete.
3. Unassociated `<label>`/`<input>` pairs on the login form (`src/pages/LoginPage.tsx:46-58`) — no `htmlFor`/`id`, so screen readers won't announce labels on focus.

### Low
4. `shared/package.json` installs `axios`/`date-fns` as devDependencies purely for type-checking, which slightly contradicts `WEB_SUPPORT.MD`'s "pure TypeScript, no runtime deps" framing of `shared` — not a bug, just a doc/reality mismatch worth tightening.

---

## Admin (`admin/`)

### High
1. **Refresh token stored in plain `localStorage`, contradicting the app's own documented design.** `ADMIN_PLAN.md:122-125` specifies an httpOnly cookie set by the backend, but `src/api/axios.ts:27,36` and `src/auth/AuthContext.tsx:23,33,51,56,59` read/write `localStorage.getItem/setItem('refresh_token', ...)`. A grep of `backend/` found no cookie-based auth implementation at all — the planned design was never built. For an admin panel with elevated privileges, a long-lived token in `localStorage` is directly exfiltrable via XSS. Fix: implement the planned httpOnly/`Secure`/`SameSite=strict` cookie flow, or explicitly document the accepted tradeoff.
2. **Admin never imports `shared` and hand-duplicates already-drifted types.** No `@shared` alias in `vite.config.ts`/`tsconfig.json`. `src/types.ts:1-6` types `AdminUser.is_admin` as `boolean` while the canonical `shared/types/auth.ts:200` types it `number`. See cross-cutting section.

### Medium
3. **No shared design-token system** — `web` defines a full brand palette (`web/src/index.css:1-21`), while `admin/tailwind.config.js:1-12` only extends `fontFamily` and uses raw Tailwind defaults throughout `Button.tsx`, `Badge.tsx`, `LoginPage.tsx`. The two front doors of the same product have no shared styling contract.
4. **Three declared dependencies never imported anywhere**: `react-hook-form`, `@hookform/resolvers`, `zod`, `@tanstack/react-table` (`package.json:19-24`) — `ADMIN_PLAN.md:19-25` documents them as the intended forms/table stack, but `UserListPage.tsx` hand-rolls a `<table>` and `LoginPage.tsx` hand-rolls form state. Fix: wire them in per the plan, or drop them.
5. **Dependency versions diverge significantly from `web`** on overlapping libraries (React 18.3 vs 19.2, react-router-dom 6.26 vs 7.18, Tailwind 3.4 vs 4.3, date-fns 3.6 vs 4.4) — and `shared/package.json` pins `date-fns ^4.4.0`, so admin is already a major behind what `shared` assumes if it ever starts importing from there.
6. **`ConfirmDialog` has no accessible modal semantics.** `src/components/ConfirmDialog.tsx:34-48` — no `role="dialog"`/`aria-modal`/`aria-labelledby`, no focus trap or restore, backdrop click doesn't close (only Escape does via a raw `document` listener).
7. Unassociated `<label>`/`<input>` pairs on the login form (`src/auth/LoginPage.tsx:39-49`), same issue as web.

### Low
8. **`useUsers()`'s `refresh` function is dead code** — defined and returned (`src/sections/users/hooks/useUsers.ts:48-50`) but never called from `UserListPage.tsx:20`, so the list doesn't reliably reflect a just-changed status after navigating back.
9. **`Avatar` crashes on a null/undefined name** — `src/components/Avatar.tsx:10-14` does `name.split(' ')` with no guard; combined with the lack of an error boundary, a loose backend payload could blank the whole users table.

---

## Shared (`shared/`)

### High
1. Type drift vs. the real backend contract for `Message`/`Conversation`/`Profile`/`PeerProfile` — see cross-cutting section for detail. This is the most load-bearing fix since everything else (wiring more consumers, extracting the API client) should happen after these are corrected.

### Medium
2. `shared/api/chat.ts:28` — `msg_type: string = 'TEXT'` default param is typed as bare `string` instead of the actual union (`'TEXT'|'AUDIO'|'IMAGE'`), losing type safety at the one call site that should enforce the enum.
3. `shared/package.json:1-9` — `axios` and `date-fns` are listed under `devDependencies` but are used at runtime by `api/*.ts` and `utils/formatDate.ts`. Works today only because `shared` is never actually npm-installed (just path-aliased by web). Fix: move to `dependencies`/`peerDependencies`.
4. No `main`/`types`/`exports` fields in `shared/package.json` and no root workspace config — see cross-cutting finding on `shared` being unreachable.

### Low
5. Several exports currently have zero consumers anywhere in the monorepo (`formatConversationTime`, `AuthTokens`, all of `Profile`/`Candidate`/`PeerProfile`) — a symptom of the wiring gap above rather than intentional dead code, but worth knowing `shared` is only ~40% used by its one real consumer (web).
