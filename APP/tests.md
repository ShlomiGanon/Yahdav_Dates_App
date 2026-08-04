# Test Plan — Yahdav Dates App

Test case ideas across `backend`, `mobile`, `web`, `admin`, and `shared`. Grounded in the actual routes/models read from the code (`backend/src/routes/*.ts`, `backend/migrations/001_initial.sql`, `backend/src/websocket/wsServer.ts`). Each case lists preconditions/steps and the expected result. IDs are stable references for tracking coverage, not an implied execution order.

Legend: **[API]** backend integration test · **[UNIT]** unit test · **[MOB]** mobile app · **[WEB]** web app · **[ADM]** admin panel · **[WS]** WebSocket · **[E2E]** cross-app flow · **[SEC]** security-focused · **[PERF]** performance/load

---

## 1. Signup — `POST /auth/signup`

- **TC-101 [API]** Valid signup (username 3-30 chars `[a-zA-Z0-9_]+`, valid email, password ≥8 chars) → `201`, body has `user_id`, `email`, `username`, `is_admin:false`, `access_token`, `refresh_token`; `user_profiles` row created with empty `name/bio/city/region`, `status:'active'`; `auth_credentials` row has a bcrypt hash (not the plaintext); a row exists in `user_sessions`.
- **TC-102 [API]** Duplicate username (case-insensitive, e.g. `Alice` vs `alice`) → `409 {error:"username_taken"}` (relies on `COLLATE NOCASE` unique index).
- **TC-103 [API]** Duplicate email (case-insensitive) → `409 {error:"email_taken"}`.
- **TC-104 [API]** Username too short (<3), too long (>30), or containing disallowed chars (space, `-`, `@`, unicode/Hebrew) → `422` with `errors` array, no row created.
- **TC-105 [API]** Invalid email format (`"not-an-email"`) → `422`, no row created.
- **TC-106 [API]** Email normalization: signup with `Alice.Test+x@GMAIL.com` → confirm `normalizeEmail()` behavior (Gmail dot/plus stripping) is what's actually desired for login lookups later; verify the stored/normalized email round-trips correctly for subsequent login.
- **TC-107 [API]** Password shorter than 8 chars → `422`, no row created.
- **TC-108 [API]** Password exactly 8 chars (boundary) → `201`.
- **TC-109 [API]** Missing each required field individually (`username`, `email`, `password` each omitted) → `422` for each, response identifies the missing field.
- **TC-110 [API]** Extra/unexpected fields in body (e.g. `is_admin:true`, `user_id:"..."`) → ignored/rejected; verify a client cannot self-elevate to admin via signup payload injection.
- **TC-111 [API]** SQL-injection-shaped input in `username`/`email` (e.g. `' OR '1'='1`) → rejected by validators or safely parameterized; no error, no injection.
- **TC-112 [API]** Very long payload / oversized `password` (e.g. 10,000 chars) → handled without crashing (DoS via bcrypt cost on huge input).
- **TC-113 [API]** Concurrent signup with the same username from two simultaneous requests (race) → exactly one succeeds with `201`, the other gets `409` (no duplicate rows from a TOCTOU gap between the `findByUsername` check and insert).
- **TC-114 [API]** Newly issued `access_token`/`refresh_token` are structurally valid JWTs; access token is usable immediately on a protected route (`GET /auth/me`) without a separate login step.
- **TC-115 [UNIT]** Password is hashed with bcrypt before storage — `auth_credentials.password_hash` is never the plaintext, and hash cost factor matches configured rounds.

## 2. Login — `POST /auth/login`

- **TC-201 [API]** Login with correct `identifier` (username) + password → `200`, tokens issued, `last_login_at` updated in `auth_credentials`.
- **TC-202 [API]** Login with correct `identifier` (email, contains `@`) + password → `200`, same as above (routing logic: `identifier.includes('@')`).
- **TC-203 [API]** Login with username that happens to contain `@`-like chars is impossible today (validator forbids it), but confirm an email-shaped username can't be created (would break the `@`-based routing) — covered by TC-104.
- **TC-204 [API]** Wrong password for existing identifier → `401 {error:"invalid_credentials"}`; verify message is identical to the "unknown identifier" case (TC-205) so it doesn't leak which part was wrong.
- **TC-205 [API]** Unknown identifier (no matching username or email) → `401 {error:"invalid_credentials"}`.
- **TC-206 [API]** Case-insensitive identifier match (`ALICE` logs in for user `alice`) → `200`.
- **TC-207 [API]** Empty `identifier` or empty `password` → `422`.
- **TC-208 [API]** Login for a `suspended` or `banned` account → currently no status check exists in the login route; verify intended behavior (should suspended/banned users be blocked at login, not just filtered from discovery?) — likely a gap to confirm with product intent.
- **TC-209 [API]** `is_admin` flag in the login response correctly reflects `auth_credentials.is_admin` for both regular and admin accounts.
- **TC-210 [API]** Timing-safe comparison: login response time for "wrong password, valid user" vs "unknown user" should not differ enough to enable user enumeration via timing attack (bcrypt compare only runs when a user is found — confirm this isn't measurably distinguishable, or add a dummy-hash compare on the not-found path).
- **TC-211 [API]** Brute-force attempt: N failed logins in a row for the same identifier from the same IP — currently unthrottled; verify/track that rate limiting gets added (see improve.md finding).
- **TC-212 [API]** Login issues a *new* session row each time (multiple concurrent sessions per user across devices) — verify old sessions from other devices remain valid after a new login (no forced single-session).

## 3. Token Refresh — `POST /auth/refresh`

- **TC-301 [API]** Valid, unexpired `refresh_token` → `200`, new `access_token` + new `refresh_token` issued (rotation), old refresh token invalidated (single-use).
- **TC-302 [API]** Reusing an already-rotated (old) refresh token a second time → rejected (`401`), and ideally the entire session family is revoked as a replay-attack signal — verify actual behavior vs. this expectation.
- **TC-303 [API]** Missing `refresh_token` in body → `400 {error:"Missing refresh_token"}`.
- **TC-304 [API]** Malformed/garbage token string → `401 {error:"invalid_token"}`.
- **TC-305 [API]** Expired refresh token (session past `expires_at`) → `401 {error:"session_expired"}`.
- **TC-306 [API]** Refresh token for a session that was already revoked/deleted (e.g. via logout) → `401 {error:"session_not_found"}`.
- **TC-307 [API]** **[SEC]** An *access* token submitted as a refresh token → must be rejected (see improve.md High #1 — currently no `type` claim distinguishes them; this test should currently **fail**, exposing the vulnerability). This is the single highest-value security regression test to add.
- **TC-308 [API]** Refresh for a user later deleted from `user_profiles` (cascade should also remove `user_sessions`) → `401`, not a `500` from a dangling FK.
- **TC-309 [API]** Refresh response includes the current `is_admin` value (not stale from token issuance) — relevant if an admin is demoted between refreshes.
- **TC-310 [API]** Concurrent refresh using the same refresh token from two simultaneous requests (double-submit race) → only one succeeds, the other gets `401` (no double-rotation race that both leaves a dangling old token accepted or issues two valid new tokens).

## 4. Logout — `POST /auth/logout`

- **TC-401 [API]** Valid `refresh_token` → `204`, session row removed from `user_sessions`; subsequent refresh with that token → `401`.
- **TC-402 [API]** Logout with no `refresh_token` in body → `204` (no-op, doesn't error).
- **TC-403 [API]** Logout with an already-invalid/expired token → `204` (idempotent, no error leak).
- **TC-404 [API]** Logout does **not** invalidate the still-live `access_token` (stateless JWT) — confirm this is accepted behavior (access tokens remain valid until natural expiry even after logout) and check the expiry window is short enough to be an acceptable risk.
- **TC-405 [MOB/WEB/ADM]** Client-side logout clears all locally stored tokens (SecureStore on mobile, localStorage on web/admin) and redirects to the login/auth stack.

## 5. Session bootstrap — `GET /auth/me`

- **TC-501 [API]** Valid access token → `200` with `user_id, email, username, is_admin`.
- **TC-502 [API]** No `Authorization` header → `401`.
- **TC-503 [API]** Malformed/expired access token → `401`.
- **TC-504 [API]** Valid token for a user subsequently deleted from `auth_credentials` → `404 {error:"not_found"}`, not a `500`.
- **TC-505 [MOB]** App cold boot with a stored refresh token but no network connectivity → user is **not** force-logged-out (regression test tied to improve.md Mobile High #2 — currently fails); app should retry or show an offline state instead of clearing tokens.
- **TC-506 [MOB]** App cold boot with a valid refresh token and no access token in memory → silently refreshes and lands the user on the main stack without seeing the login screen.
- **TC-507 [MOB]** App cold boot with an expired/revoked refresh token → correctly routed to the auth stack.

## 6. My Profile — `GET/PUT /users/me`

- **TC-601 [API]** `GET /users/me` for an authenticated user with a complete profile → `200` with all fields.
- **TC-602 [API]** `GET /users/me` for a user whose profile row is somehow missing (shouldn't happen given signup always creates one, but test the 404 path) → `404`.
- **TC-603 [API]** `PUT /users/me` updating a single field (e.g. only `bio`) → only that field changes, others untouched, `updated_at` bumped.
- **TC-604 [API]** `PUT /users/me` with an **empty body `{}`** → currently produces malformed SQL / 500 (improve.md Backend High #6) — this test should currently **fail** and is the regression test for that fix; expected correct behavior is a `200` no-op or `422`.
- **TC-605 [API]** `PUT /users/me` with only unrecognized keys (e.g. `{"foo":"bar"}`) → same empty-`fields` bug path as TC-604.
- **TC-606 [API]** `name` boundary: empty string → `422` (min 1); exactly 80 chars → `200`; 81 chars → `422`.
- **TC-607 [API]** `bio` boundary: exactly 500 chars → `200`; 501 chars → `422`; bio can be an empty string (no `min` constraint) → `200`.
- **TC-608 [API]** `gender` must be one of `male|female|other`; any other value (`"Male"` wrong case, `"nonbinary"`, empty string) → `422`.
- **TC-609 [API]** `date_of_birth` format `YYYY-MM-DD` — valid date → `200`; malformed (`"01-01-2000"`, `"2000/01/01"`) → `422`; syntactically valid but impossible date (`"2000-02-30"`) → currently only regex-checked, not calendar-validated — verify whether this should be rejected.
- **TC-610 [API]** `date_of_birth` in the future, or implying age < 18 (or whatever the platform's minimum age is) → no explicit backend check found; verify whether age-gating is enforced anywhere (likely a gap worth flagging).
- **TC-611 [API]** `city`/`region` boundary: empty string → `422` (min 1); 80/81 char boundary same as `name`.
- **TC-612 [API]** Fields not in the allowlist (`user_id`, `status`, `photo_url`, `registered_at`) sent in the PUT body → silently ignored, cannot be overwritten via this endpoint (verify `status` in particular can't be self-escalated to bypass admin suspension).
- **TC-613 [API]** Unauthenticated request to either endpoint → `401`.
- **TC-614 [MOB]** `MyProfileScreen` round-trip: edit each field in the UI, save, re-fetch, and confirm the displayed values match what was saved (including Hebrew text in `name`/`bio`/`city`).

## 7. Main Photo — `POST /users/me/photo`

- **TC-701 [API]** Upload a valid JPEG/PNG under the size limit → `201`/`200` with `{photo_url}`; file appears under `/uploads/`; `user_profiles.photo_url` updated.
- **TC-702 [API]** Uploading a new main photo when one already exists → old file is deleted from disk (`deleteFileByUrl`) and replaced; verify no orphaned file left behind.
- **TC-703 [API]** No file attached (`missing_file`) → `422`.
- **TC-704 [API]** Disallowed file type (e.g. `.pdf`, `.exe`, `.svg` with embedded script, `.gif`) → `415 {error:"invalid_file_type"}`.
- **TC-705 [API]** File exceeding the size limit → `413 {error:"file_too_large"}`.
- **TC-706 [SEC]** Upload a file with a spoofed MIME type / double extension (`photo.jpg.exe`, or a valid JPEG magic-number file whose extension is `.php`) → verify server validates actual content type, not just the client-supplied `Content-Type` header or filename extension, to prevent stored-payload attacks via the static `/uploads` mount.
- **TC-707 [SEC]** Path traversal in filename (`../../etc/passwd` as original filename) → verify the generated stored filename is server-controlled (UUID-based) and the original name can't influence the storage path.
- **TC-708 [API]** Unauthenticated upload attempt → `401`.
- **TC-709 [MOB]** Upload flow shows a loading state, then the new photo renders immediately without requiring app restart/refetch.
- **TC-710 [MOB]** Corrupt/unreadable image selected from the device gallery → `resizePhoto` failure is caught and surfaces a user-facing error instead of an unhandled rejection (regression test for improve.md Mobile Medium #8).

## 8. Additional Photos — `GET/POST/DELETE /users/me/photos`

- **TC-801 [API]** `GET /me/photos` for a user with 0 photos → `200 []`.
- **TC-802 [API]** `POST /me/photos` up to the 4-photo limit → each succeeds with `201` and the new `Photo` object.
- **TC-803 [API]** `POST /me/photos` on the 5th attempt (already at 4) → `422 {error:"photo_limit_reached"}`, and the just-uploaded file is deleted from disk (verify no orphaned file on rejection).
- **TC-804 [API]** `DELETE /me/photos/:photo_id` with a valid UUID owned by the caller → `200 {ok:true}`, file removed from disk and DB.
- **TC-805 [API]** `DELETE /me/photos/:photo_id` with a non-UUID path param → `422` (validator).
- **TC-806 [API]** `DELETE /me/photos/:photo_id` for a UUID that doesn't exist → `404`.
- **TC-807 [SEC]** `DELETE /me/photos/:photo_id` for a photo that exists but belongs to a **different** user → must not delete it; verify the query scopes by `user_id` as well as `photo_id` (IDOR check) — confirm expected `404`, not `200`.
- **TC-808 [API]** After deleting a photo, the count resets so a 5th upload becomes possible again (limit is a live count, not a lifetime cap).
- **TC-809 [API]** Concurrent uploads of photo #4 and #5 racing simultaneously when currently at count 3 → at most 4 succeed total (no race allowing 5+ past the `countPhotos(sub) >= 4` check-then-act gap).
- **TC-810 [MOB]** `AdditionalPhotosScreen` grid reflects add/remove immediately and disables the "add" affordance once at 4/4.

## 9. Discover / Candidate Feed — `GET /users/discover`

- **TC-901 [API]** Default call (no `page`/`limit`) → `200`, array of up to 20 candidates.
- **TC-902 [API]** Caller's own profile never appears in their own discover results.
- **TC-903 [API]** A user with `status != 'active'` (suspended/banned) never appears as a candidate to anyone.
- **TC-904 [API]** A user the caller has blocked does not appear in the caller's discover feed.
- **TC-905 [API]** A user who has blocked the caller does not appear in the caller's discover feed either (mutual exclusion — verify both directions of `user_blocks` are checked, per the `NOT IN` subqueries in both directions).
- **TC-906 [API]** Pagination: `page=1&limit=2` then `page=2&limit=2` on a dataset of 5 active users → no duplicate candidates across pages, correct total ordering by `registered_at DESC`.
- **TC-907 [API]** `limit` boundary: `limit=100` → `200`; `limit=101` → `422`; `limit=0` → `422` (min 1).
- **TC-908 [API]** `page=0` or negative → `422`.
- **TC-909 [API]** Empty result set (no eligible candidates left) → `200 []`, not an error.
- **TC-910 [API]** Candidate objects never include the target's `email`, `password_hash`, or other `auth_credentials` fields — only public profile fields.
- **TC-911 [API]** Unauthenticated request → `401`.
- **TC-912 [MOB]** `DiscoverScreen` correctly requests the next page on scroll/swipe-through and doesn't re-show already-seen candidates within a session.
- **TC-913 [API]** After a user blocks someone mid-session, that person disappears from subsequent discover calls (no caching staleness).

## 10. Peer Profile & Peer Photos — `GET /users/:id`, `GET /users/:id/photos`

- **TC-1001 [API]** Valid UUID for an existing, active user → `200` with public profile fields.
- **TC-1002 [API]** Non-UUID `:id` (e.g. `"abc"`, or the literal string `"discover"` colliding with route ordering) → `422`, and specifically verify the route ordering comment in `profile.routes.ts` ("`/:id` routes MUST come after `/me/*` and `/discover`") actually holds — regression test that `GET /users/discover` and `GET /users/me` are never swallowed by the `:id` route.
- **TC-1003 [API]** UUID that doesn't exist → `404`.
- **TC-1004 [API]** Peer profile for a user the caller has blocked (or who has blocked the caller) — verify current behavior (profile still viewable via direct link even if excluded from discover — is that intended?).
- **TC-1005 [API]** `GET /:id/photos` returns `{name, photos}` shape (not the same shape as `/me/photos`) — verify mobile's `usePeerPhotos` reads both fields correctly (already called out as a documented gotcha in the code comment).
- **TC-1006 [API]** `GET /:id/photos` for a peer with 0 additional photos → `{name, photos: []}`.
- **TC-1007 [MOB]** `PeerProfileScreen` → `PeerPhotosScreen` navigation passes the correct `id` and renders the peer's name/photos, not the viewer's own.

## 11. Block User — `POST /users/:id/block`

- **TC-1101 [API]** Valid block of another user → `200 {ok:true}`, row inserted into `user_blocks`.
- **TC-1102 [API]** Blocking yourself (`sub === :id`) → `422 {error:"cannot_block_self"}`.
- **TC-1103 [API]** Blocking the same user twice (duplicate) → verify behavior against the composite PK (`blocker_id, blocked_id`) — likely a constraint conflict; confirm it's handled gracefully (idempotent `200`, not a raw `500`).
- **TC-1104 [API]** Non-UUID `:id` → `422`.
- **TC-1105 [API]** Blocking a nonexistent user ID → verify behavior (currently no existence check before `addBlock` — likely inserts a dangling-looking row that silently has no effect since FK exists on `user_profiles`; should probably be `404`).
- **TC-1106 [API]** After blocking, immediately verify: (a) blocked user vanishes from discover (TC-904), (b) `POST /chat/:blocked_id` is rejected with `403` (TC-1210), (c) existing chat history with them is still viewable or not — decide/verify intended behavior.
- **TC-1107** There is currently no `unblock` endpoint in the route list — confirm whether that's intentional (permanent block) or a missing feature; if missing, that's a product gap worth flagging, not just a test gap.
- **TC-1108 [MOB]** Blocking a peer from `PeerProfileScreen`/`ChatScreen` shows a confirmation prompt before firing the request (destructive action) and navigates away afterward.

## 12. Chat — REST (`/chat/*`)

- **TC-1201 [API]** `GET /chat/conversations` for a user with existing conversations → `200`, list ordered by recency, includes peer info + last message preview + unread count.
- **TC-1202 [API]** `GET /chat/conversations` for a user with zero conversations → `200 []`.
- **TC-1203 [API]** `GET /chat/:peer_id` with default pagination → up to 20 most recent messages between the two users, correctly excludes messages involving other users.
- **TC-1204 [API]** `GET /chat/:peer_id?limit=&before=` cursor pagination — fetching "before" a given `message_id` returns strictly older messages, no duplicates/gaps when paging through full history.
- **TC-1205 [API]** `limit` boundary (1–100) enforced; `before` must be a UUID — malformed cursor → `422`.
- **TC-1206 [API]** `GET /chat/:peer_id` for a `peer_id` the caller has never messaged → `200 []` (not `404`).
- **TC-1207 [API]** `POST /chat/:peer_id` valid `content` (≤4000 chars) → `201`, message persisted, `msg_type` defaults to `TEXT` when omitted.
- **TC-1208 [API]** `content` boundary: exactly 4000 chars → `201`; 4001 chars → `422`; empty/whitespace-only → `422` (`trim().notEmpty()`).
- **TC-1209 [API]** `msg_type` must be one of `TEXT|AUDIO|IMAGE`; any other value → `422`.
- **TC-1210 [API]** Sending to a blocked peer (either direction) → `403 {error:"blocked"}`, no message persisted.
- **TC-1211 [API]** **[SEC]** Sending a message to yourself (`peer_id === sub`) → currently unvalidated at the route level, relies on the DB `CHECK (sender_id <> recipient_id)` constraint and produces a raw, unhandled `500` (improve.md Backend High #3 / Medium #9) — regression test for adding an explicit `422` check.
- **TC-1212 [API]** Sending to a nonexistent `peer_id` (valid UUID format, no matching row) → same as TC-1211, currently an FK-constraint `500` instead of a clean `404`.
- **TC-1213 [API]** After a successful send, if the recipient is connected via WS, the message is pushed to them in real time (no separate poll needed) — verify via a WS test double.
- **TC-1214 [API]** After a successful send, if the recipient is **offline** and has a registered `expo_push_token`, a push notification is dispatched with a truncated (≤60 char + ellipsis) preview of the content.
- **TC-1215 [API]** `PUT /chat/:peer_id/read` marks all messages from that peer as read (`read_at` set); subsequent `GET /chat/conversations` reflects `unread_count: 0` for that thread.
- **TC-1216 [API]** `PUT /chat/:peer_id/read` when there are no unread messages → `200 {ok:true}`, no-op.
- **TC-1217 [API]** Unauthenticated access to any `/chat/*` route → `401`.
- **TC-1218 [SEC]** **[IDOR]** User A attempts to read User B's and User C's conversation by manipulating `peer_id` — confirm messages are always scoped to `(sub, peer_id)` pairs and A can never see a conversation they're not part of.

## 13. Chat — WebSocket (`/ws`)

- **TC-1301 [WS]** Connect with a valid, unexpired access token in the `?token=` query param → connection accepted, `wsManager.register` called.
- **TC-1302 [WS]** Connect with no token, an expired token, or a garbage token → connection closed with code `4001` immediately.
- **TC-1303 [WS]** **[SEC]** Connect using a *refresh* token instead of an access token in `?token=` → currently succeeds because `verifyAccess` doesn't check a `type` claim (same root cause as TC-307) — regression test for that fix.
- **TC-1304 [WS]** Send `{"type":"ping"}` → receive `{"type":"pong"}`.
- **TC-1305 [WS]** Send a valid `{peer_id, content}` frame → sender receives `{"type":"ack", message_id}`, and if the recipient is connected they receive the full message frame in real time.
- **TC-1306 [WS]** Send a frame to a blocked peer over WS → `{"type":"error","code":"blocked",...}`, no message persisted (mirrors TC-1210 for the WS transport).
- **TC-1307 [WS]** **[SEC]** Send a frame with `content` longer than 4000 chars, or `msg_type` outside `TEXT|AUDIO|IMAGE` → currently **not validated** on the WS path (improve.md High, cross-cutting) — this should be rejected the same way the REST endpoint rejects it; write the test now so it starts red and turns green once validation is added.
- **TC-1308 [WS]** **[SEC]** Send `{peer_id: <self>, content:"hi"}` (self-message via WS) → currently reaches `MessageModel.send` and hits the same unguarded `CHECK` constraint as TC-1211, this time inside a raw `ws.on('message')` callback with **no try/catch** — verify whether this crashes the whole process (improve.md Backend High #3) or just the one connection; this is the top-priority regression test for that finding.
- **TC-1309 [WS]** Send malformed (non-JSON) data over the socket → handled gracefully (silently ignored per current code), connection stays open.
- **TC-1310 [WS]** Send a JSON frame with neither `peer_id` nor `content` (e.g. some other event shape) → ignored, no crash, no ack.
- **TC-1311 [WS]** **[MOB]** A non-chat frame shape (hypothetically a future `{type:"typing", sender_id:"..."}` frame) reaching the mobile client's `useMessages` handler — verify it does *not* get appended to the visible message list (regression test for improve.md Mobile High #3 discriminator gap).
- **TC-1312 [WS]** Client disconnects (app backgrounded / network drop) → server-side `wsManager.unregister` fires on `close`; a message sent to that user afterward correctly falls back to the push-notification path instead of silently being lost.
- **TC-1313 [WS] [MOB]** Mobile reconnect logic: kill the socket (simulate network blip), verify exponential backoff reconnect eventually re-establishes the connection and resumes receiving messages, tested identically for both `useMessages` and `useConversations` (regression coverage for the duplicated-logic finding — a bug fixed in one must be provably fixed in both, or better, both should share one hook).
- **TC-1314 [WS]** Two devices/tabs authenticated as the same user connect simultaneously → both receive real-time messages (multi-connection fan-out), or verify/document the actual single-connection-per-user behavior if `wsManager.register` overwrites rather than appends.
- **TC-1315 [WS] [PERF]** Rapid-fire sending 50 messages in under a second from one client → server doesn't crash, ordering is preserved, no dropped acks.

## 14. Admin — User List/Search — `GET /admin/users`, `GET /admin/users/:id`

- **TC-1401 [API]** Admin-authenticated request, no `search` → `200 {total, users}`, paginated by `limit`/`offset` (defaults 50/0).
- **TC-1402 [API]** Non-admin authenticated user calling any `/admin/*` route → `403` (verify `requireAdmin` middleware actually blocks, not just hides UI).
- **TC-1403 [API]** Unauthenticated request → `401`.
- **TC-1404 [API]** `search` matches partial, case-insensitive substrings across `name`, `city`, `username`, `email` → correct filtered results.
- **TC-1405 [API]** `search` with no matches → `200 {total:0, users:[]}`.
- **TC-1406 [API]** `search` combined with `offset`/`limit` — verify pagination is applied *after* filtering (slice on `filtered`, not on the raw 10,000-row fetch) and totals reflect the filtered count, not the global count.
- **TC-1407 [API] [PERF]** `search` behavior at scale (e.g. 10,000+ real user rows) — the current implementation loads up to 10,000 profiles into memory and does one `findById` call per row (improve.md Backend Medium #8); write a load test that measures response time / DB round-trips as the table grows, to have a concrete before/after when this gets fixed.
- **TC-1408 [API]** `limit` boundary 1–200; `offset` ≥0 — out-of-range values → `422`.
- **TC-1409 [API]** `GET /admin/users/:id` for a valid existing user → full detail including `username`, `email`, `is_admin`, `last_login_at`.
- **TC-1410 [API]** `GET /admin/users/:id` for a nonexistent UUID → `404`.
- **TC-1411 [API]** `GET /admin/users/:id` for a non-UUID param → `422`.
- **TC-1412 [ADM]** Admin panel's user list renders correctly for 0 users, 1 user, and a full page of 50; search box debounces/filters as expected.

## 15. Admin — Status & Delete — `PUT /admin/users/:id/status`, `DELETE /admin/users/:id`

- **TC-1501 [API]** Set a user's status to `suspended` → `200`, `user_profiles.status` updated, `updated_at` bumped; user disappears from discover (cross-check with TC-903) but can they still log in? Verify against TC-208.
- **TC-1502 [API]** Set status to `banned` and back to `active` → both transitions succeed.
- **TC-1503 [API]** `status` value outside `active|suspended|banned` → `422`.
- **TC-1504 [API]** Admin attempts to change **their own** status → `422 {error:"cannot_change_own_status"}` (self-lockout protection).
- **TC-1505 [API]** Status change on a nonexistent user ID → `404`.
- **TC-1506 [API]** `DELETE /admin/users/:id` for an existing user → `204`, cascading deletes remove `auth_credentials`, `user_photos`, `user_sessions`, `user_blocks`, and their `direct_messages` (verify `ON DELETE CASCADE` actually cascades through every FK, including messages where the deleted user was either sender or recipient).
- **TC-1507 [API]** Admin attempts to **delete themselves** → `422 {error:"cannot_delete_self"}`.
- **TC-1508 [API]** Delete on a nonexistent user ID → `404`.
- **TC-1509 [SEC]** After deletion, that user's still-valid access token (issued before deletion, not yet expired) is used on a protected route → verify it's rejected cleanly (`404`/`401`) rather than crashing on a null profile lookup.
- **TC-1510 [API]** Deleting a user who is mid-conversation with an online peer — verify the peer's open chat screen / WS connection doesn't crash when referencing the now-deleted user (e.g. via a stale conversation list entry).
- **TC-1511 [ADM]** Status/Delete actions in the admin UI are gated behind a confirmation dialog (`ConfirmDialog`) before firing; verify Escape and backdrop-click behavior, and that the dialog is keyboard-operable (ties to improve.md Admin Medium #6 accessibility gap).
- **TC-1512 [ADM]** After a status change on the detail page, navigating back to the list reflects the new status without a manual refresh (regression test for improve.md Admin Low #8 — the unused `refresh()`).

## 16. Push Notifications — `/users/me/push-token`

- **TC-1601 [API]** `POST /me/push-token` with a valid `token` and optional `platform` (`ios`/`android`) → `200`, token stored on the profile.
- **TC-1602 [API]** `POST /me/push-token` with empty `token` → `422`.
- **TC-1603 [API]** `platform` value outside `ios|android` → `422`; omitted `platform` → still succeeds.
- **TC-1604 [API]** `DELETE /me/push-token` clears the stored token → subsequent offline-message delivery to this user does **not** attempt a push (verify `pushService` is skipped when `expo_push_token` is null).
- **TC-1605 [API]** Registering a new token overwrites the previous one (single token per user, e.g. after reinstall) — verify old token isn't still used.
- **TC-1606 [API]** `sendPushNotification` failure (e.g. Expo API returns an error/invalid token) does not throw unhandled — the triggering `POST /chat/:peer_id` call still returns `201` to the sender even if the push itself fails.
- **TC-1607 [MOB]** Push token is (re-)registered on app launch/login and unregistered on logout.

## 17. Cross-cutting security & authorization

- **TC-1701 [SEC]** Every non-auth route rejects requests with no `Authorization` header, a malformed header (`"Bearer"` with no token, wrong scheme), and an expired token — run as a parameterized sweep across all routes in `profile.routes.ts`, `chat.routes.ts`, `admin.routes.ts`.
- **TC-1702 [SEC]** `requireAdmin` is verified independently of `authenticate` — a valid non-admin token must fail admin routes even though it passes general authentication (distinguish 401 vs 403 paths).
- **TC-1703 [SEC]** JWT signed with a different/invalid secret (tampered token) → rejected everywhere.
- **TC-1704 [SEC]** JWT with an altered payload but original signature stripped/re-signed with `alg:none` → rejected (verify the JWT library is configured to reject `none` algorithm).
- **TC-1705 [SEC]** CORS: confirm what origins are actually allowed in production given `ADMIN_CORS_ORIGIN` is currently dead config with no `cors` middleware installed (improve.md Backend Medium #11) — until fixed, document current exposure (effectively no CORS restriction, or same-origin only, whichever `app.ts` actually defaults to).
- **TC-1706 [SEC]** Verify `express.json()` body size limits are enforced (oversized JSON payload doesn't exhaust memory).
- **TC-1707 [SEC]** Verify no endpoint leaks `password_hash` in any response (grep every route's response shape).
- **TC-1708 [SEC]** Verify rate limiting (once added per improve.md) actually throttles `/auth/login`, `/auth/signup`, `/auth/refresh` per IP and/or per identifier without locking out legitimate concurrent users on shared IPs (NAT/office networks).
- **TC-1709 [SEC]** Static `/uploads` mount: confirm files are only ever accessible by guessing/knowing a UUID filename (no directory listing enabled).

## 18. Data integrity / DB-level

- **TC-1801 [UNIT]** `direct_messages` CHECK constraint (`sender_id <> recipient_id`) rejects a raw insert attempt at the DB layer, independent of the app-level validation gap (belt-and-suspenders test).
- **TC-1802 [UNIT]** All FK `ON DELETE CASCADE` relationships (`auth_credentials`, `user_photos`, `user_sessions`, `user_blocks` both directions, `direct_messages` both directions) actually cascade when the parent `user_profiles` row is deleted — write one test per table.
- **TC-1803 [UNIT]** `schema_version` tracking behaves correctly across multiple pending migrations run in a single boot (regression test for improve.md Backend High #4 — currently broken for 2+ files; write this test now with two dummy migration files so it's ready the moment `002_*.sql` is added).
- **TC-1804 [UNIT]** Running the migration runner twice against an already-migrated DB is idempotent (no duplicate `CREATE TABLE` errors).
- **TC-1805 [UNIT]** Unique index behavior: `username`/`email` uniqueness is enforced `COLLATE NOCASE` at the DB level even if app-level checks were bypassed (defense in depth).
- **TC-1806 [UNIT]** `user_blocks` composite PK prevents a literal duplicate `(blocker_id, blocked_id)` insert — confirms/contradicts TC-1103's expected app-level handling.

## 19. Mobile app — navigation, screens, UX

- **TC-1901 [MOB]** Fresh install → `WelcomeScreen` → `SignupScreen` → successful signup lands the user directly in the main stack (no separate login step required), matching the "profile fields filled later" signup design.
- **TC-1902 [MOB]** `AuthStack` ↔ `MainStack` transition is driven correctly by `RootNavigator` based on token presence — no flash of the wrong stack on boot.
- **TC-1903 [MOB]** Back-navigation (hardware back on Android, swipe-back on iOS) from every screen behaves sensibly — no dead ends, no accidental logout.
- **TC-1904 [MOB]** `MenuScreen` logout option round-trips through `POST /auth/logout` and clears local tokens before navigating to `WelcomeScreen`.
- **TC-1905 [MOB]** `ChatHistoryScreen` list updates live when a new message arrives while the screen is focused (via the shared/duplicated WS hook) and shows correct unread badges.
- **TC-1906 [MOB]** `ChatScreen` optimistic send: message appears immediately with a "sending" indicator, then reconciles with the server-confirmed message — verify no duplicate bubble and no ID collision on rapid sends (regression test for improve.md Mobile Medium #10, timestamp-only tmp IDs).
- **TC-1907 [MOB]** `ChatScreen` failed send (network drop mid-send) shows a retry affordance, doesn't silently lose the message.
- **TC-1908 [MOB]** Signup form client-side `deriveUsername` behavior when two different emails derive the same local-part (e.g. `john@gmail.com`, `john@yahoo.com`) — verify the resulting 409 error message is accurate (email vs. username conflict) rather than misleading (improve.md Mobile Low #14).
- **TC-1909 [MOB]** App backgrounded and resumed after >refresh-token-adjacent time window — session either silently refreshes or routes cleanly to login, never shows a broken/stale screen.
- **TC-1910 [MOB]** Airplane-mode / no-connectivity states across every data-fetching screen show the existing `ErrorCard`/loading states rather than crashing (and specifically that boot-time doesn't force logout — TC-505).
- **TC-1911 [MOB]** Uncaught render error anywhere in the tree — currently no top-level `ErrorBoundary` (improve.md Mobile Low #15) — verify current behavior is the RN red-screen/crash, as a baseline before that gap is closed.

## 20. Mobile app — RTL / Hebrew / i18n

- **TC-2001 [MOB]** All screens render correctly under `I18nManager.forceRTL(true)` — layout mirrors correctly (icons, navigation chevrons, list item alignment).
- **TC-2002 [MOB]** `HebrewInput` fields: typing Hebrew text shows correct right-aligned text and correct cursor position/direction.
- **TC-2003 [MOB]** Mixed Hebrew/Latin input (e.g. typing an email address, which is LTR, inside an RTL-context field) — verify cursor doesn't jump unexpectedly (regression test tied to improve.md Mobile Medium #6, missing `writingDirection:'rtl'`).
- **TC-2004 [MOB]** All user-facing error/success messages (e.g. `"האימייל כבר קיים במערכת"`) display correctly with proper Hebrew text rendering across device font settings/sizes.
- **TC-2005 [MOB]** Long Hebrew names/bios wrap correctly in RTL without overflowing or clipping in profile cards.
- **TC-2006 [WEB/ADM]** Confirm whether the web and admin apps need RTL support too (product question) and, if so, whether it's implemented — currently unclear from the review; worth a dedicated pass.

## 21. Web app (`web/`)

- **TC-2101 [WEB]** **[REGRESSION]** Login button actually submits the form — currently a no-op (`onPress={() => {}}` with `type="button"` hardcoded, improve.md Web High #1); test both "click button" and "press Enter in a field" paths, only the latter currently works.
- **TC-2102 [WEB]** Login form validation: empty fields, wrong credentials, network failure all show appropriate inline errors.
- **TC-2103 [WEB]** Successful login persists tokens and redirects to the discover/home page.
- **TC-2104 [WEB]** `DiscoverPage`, `ProfilePage`, `PeerProfilePage`, `ChatHistoryPage`, `ChatPage` — currently static placeholder stubs with no API wiring (improve.md Web Medium #2); once implemented, each needs the same loading/empty/error/success coverage as its mobile counterpart (cross-reference sections 6–13 above, web-flavored).
- **TC-2105 [WEB]** `PhotoUpload` component (currently unused/unwired) — once wired into a page, needs file-type/size validation coverage mirroring TC-704/705.
- **TC-2106 [WEB]** Keyboard accessibility: tab order through the login form reaches the submit button and label/input pairs are correctly associated (regression test for improve.md Web Medium #3).
- **TC-2107 [WEB]** Session persistence across a page refresh (token in memory/localStorage survives reload, `/auth/me` re-validates).
- **TC-2108 [WEB]** Responsive layout at common breakpoints (mobile web viewport, tablet, desktop) for whichever pages are implemented.
- **TC-2109 [WEB]** Uncaught render error — no top-level `ErrorBoundary` currently exists; same baseline test as TC-1911, web-flavored.

## 22. Admin panel (`admin/`)

- **TC-2201 [ADM]** Login with valid admin credentials → lands on the user list; login with a **non-admin** account that nonetheless has valid credentials → verify whether the panel rejects it client-side, and confirm the backend still enforces `requireAdmin` regardless (defense in depth, ties to TC-1402).
- **TC-2202 [ADM]** Refresh-token storage: currently plain `localStorage` despite `ADMIN_PLAN.md` documenting httpOnly cookies (improve.md Admin High #1) — write an XSS-simulation test (inject a script that reads `localStorage.refresh_token`) to make the risk concrete, and re-run it once the cookie-based flow is implemented to confirm it's closed.
- **TC-2203 [ADM]** User list search, pagination, and empty-state rendering match the backend behavior verified in section 14.
- **TC-2204 [ADM]** User detail page: viewing, changing status, and deleting a user each show correct confirmation UX and success/error toasts/messages.
- **TC-2205 [ADM]** Admin attempting to change their own status or delete themselves via the UI — button should be disabled/hidden, and even if forced via devtools, the backend rejects it (TC-1504/1507).
- **TC-2206 [ADM]** Session bootstrap on page load re-validates the token via `/auth/me` and redirects to login if invalid/expired.
- **TC-2207 [ADM]** `Avatar` component with a user that has an empty/null `name` — currently can throw (improve.md Admin Low #9); verify it degrades gracefully instead of blanking the table.
- **TC-2208 [ADM]** Keyboard/focus behavior of `ConfirmDialog` — Escape closes it, backdrop click closes it (currently doesn't — improve.md Admin Medium #6), focus moves into the dialog on open and returns to the triggering element on close.

## 23. Cross-app / end-to-end flows

- **TC-2301 [E2E]** Full happy path: User A signs up (mobile) → completes profile + uploads a main photo → appears in User B's discover feed → B views A's peer profile and photos → B sends a chat message → A receives it in real time (WS) if online, or via push if backgrounded → A replies → both see updated `ChatHistoryScreen`/unread counts.
- **TC-2302 [E2E]** Blocking flow: A and B are mid-conversation → A blocks B → B's further messages to A are rejected (`403`) both via REST and WS → B no longer appears in A's discover feed → A optionally still sees prior message history (verify intended behavior).
- **TC-2303 [E2E]** Admin moderation flow: Admin views a reported/suspicious user in the admin panel → suspends them → that user disappears from all other users' discover feeds → (verify/decide) whether the suspended user can still log in and what UX they see if so.
- **TC-2304 [E2E]** Admin deletes a user who has an active chat open with another currently-online user → the online peer's app doesn't crash, and any subsequent action referencing the deleted user degrades gracefully (404s, not 500s).
- **TC-2305 [E2E]** Token expiry mid-session: user has the app open with a soon-to-expire access token → access token expires → next API call triggers a silent refresh via the interceptor → call succeeds without the user noticing (test both mobile and web/admin interceptor implementations separately, since they're independently maintained per improve.md).
- **TC-2306 [E2E]** Multi-device: same user logged in on mobile and web simultaneously → sending a message from one surfaces it in the other's conversation list on next load (no requirement for live sync between web/mobile unless product intends it — verify actual expectation).
- **TC-2307 [E2E]** Full account lifecycle: signup → use app → self-initiated logout → login again with the same credentials → all prior data (profile, photos, chat history) is intact and correctly displayed.

## 24. Performance & load

- **TC-2401 [PERF]** `GET /users/discover` response time as `user_profiles` grows from 100 → 10,000 → 100,000 active rows (index usage on `status`/`registered_at` — verify an index actually exists or is needed).
- **TC-2402 [PERF]** `GET /admin/users?search=` response time at 10,000+ rows — concrete before/after benchmark for the improve.md N+1/in-memory-scan finding (TC-1407).
- **TC-2403 [PERF]** WebSocket server behavior under many concurrent connections (e.g. 500 simulated clients) — connection registration/unregistration doesn't leak memory in `wsManager` over repeated connect/disconnect cycles.
- **TC-2404 [PERF]** Chat history pagination (`GET /chat/:peer_id`) on a conversation with tens of thousands of historical messages — verify the `before`-cursor index (`idx_messages_pair`/`idx_messages_pair2`) keeps this fast rather than degrading linearly.
- **TC-2405 [PERF]** Bulk photo upload/delete stress test — concurrent multi-user photo operations don't corrupt the on-disk `/uploads` state or leave orphaned files under load.

## 25. Non-functional / resilience

- **TC-2501** Server restart mid-flight: an in-progress WS connection is dropped and mobile's reconnect logic recovers without requiring a manual app restart.
- **TC-2502** Database file lock contention (SQLite, single-writer): concurrent writes from multiple simultaneous requests (e.g. two users sending messages at once) don't produce `SQLITE_BUSY` errors surfaced as raw 500s to the client — verify retry/backoff or WAL mode is configured.
- **TC-2503** Disk-full or `/uploads` directory unwritable → photo upload fails with a clean `5xx` and a sensible error, not a crash.
- **TC-2504** Expo push service unreachable/erroring → doesn't block or fail the underlying `POST /chat/:peer_id` request (already partially covered by TC-1606; add an explicit chaos test that simulates the push provider timing out).
- **TC-2505** Clock skew between client and server doesn't break token expiry checks in a way that either logs users out early or lets clearly-expired tokens through.

## 26. Wide-net edge cases

Cases that don't map to one feature area but are the kind of thing that actually breaks real systems — grouped by category.

### 26.1 Unicode, text, and encoding

- **TC-2601** Emoji in `name`/`bio`/chat `content` (single emoji, ZWJ compound emoji like family/flag sequences) — stored and rendered without corrupting byte length checks (JS `.length` counts UTF-16 code units, not graphemes — verify `isLength({max:...})` validators don't miscount surrogate-pair/ZWJ emoji and either wrongly reject valid-length text or wrongly accept oversized text).
- **TC-2602** Right-to-left override / bidi control characters (`‮`, etc.) injected into `name` or chat `content` — verify these can't be used to visually spoof text (e.g. making a message look like it says something other than what it contains) in the mobile/web/admin UI.
- **TC-2603** Null byte (` `) embedded in any string field — rejected or safely stripped, not passed through to SQLite/filesystem (photo filenames, log lines).
- **TC-2604** Whitespace-only strings (`"   "`, tabs, newlines) in fields that require non-empty content (`chat.content`, `signup.username`) — confirm `trim()` runs *before* the `notEmpty()`/length check, not after, so `"   "` is correctly rejected rather than accepted as 3 chars.
- **TC-2605** Leading/trailing whitespace in `username`/`email` at signup and login (`" alice "`) — verify trimming is applied consistently on both write (signup) and read (login lookup), so a user can't accidentally create an unloginable account.
- **TC-2606** Mixed Hebrew + emoji + Latin + numerals in a single chat message or bio — rendering, storage, and truncation (e.g. the 60-char push-notification preview slice at `chat.routes.ts:67`) don't split a multi-byte character or emoji ZWJ sequence mid-codepoint, producing a mangled preview or broken glyph.
- **TC-2607** Unicode-confusable / homoglyph usernames or emails (e.g. Cyrillic `а` vs Latin `a`) — two visually-identical-but-distinct usernames are currently allowed as separate accounts since the DB match is exact/NOCASE, not confusable-aware; document as a known enumeration/impersonation risk, not necessarily a bug to fix immediately.
- **TC-2608** Extremely long single "word" with no spaces in a chat message or bio (e.g. 4000 non-breaking characters) — UI doesn't overflow/break layout (mobile `ChatScreen` bubble width, web/admin text wrapping).
- **TC-2609** Surrogate-pair splitting at exact length boundaries — a 4000-character message that ends mid-emoji at position 4000/4001 — verify the truncation/validation boundary doesn't produce an invalid half-surrogate stored in SQLite.

### 26.2 Numeric, date, and boundary values

- **TC-2610** `date_of_birth` exactly at a leap-year boundary (`"2000-02-29"` valid, `"2001-02-29"` invalid) — current regex-only validation (`/^\d{4}-\d{2}-\d{2}$/`) accepts both; verify whether calendar-correctness validation is needed.
- **TC-2611** `date_of_birth` of `"0000-01-01"`, `"9999-12-31"`, or other absurd-but-regex-valid dates — accepted today; decide whether a sane min/max year range should be enforced.
- **TC-2612** Age boundary exactly at whatever the platform's minimum age is (e.g. exactly 18 years old today, one day before turning 18, one day after) — confirmed gap from TC-610; write the boundary tests once age-gating exists.
- **TC-2613** Pagination boundary: requesting the exact last page where the result count is less than `limit` (partial page) — no error, correct partial array, `total` still accurate.
- **TC-2614** Pagination `page`/`offset` beyond the last page (e.g. `page=999` on a 5-user table) — `200` with an empty array, not `404`/`500`.
- **TC-2615** Integer overflow / absurd values for `page`, `limit`, `offset` (e.g. `limit=999999999999999`) — validators cap them (`max:100`/`max:200`), but verify a value like `1e300` or a non-numeric string coerced via `toInt()` doesn't produce `NaN` flowing into the SQL `LIMIT`/`OFFSET` clause.
- **TC-2616** Timestamps stored as `TEXT` ISO-8601 UTC — verify ordering (`ORDER BY created_at DESC`) is correct across a DST transition and across users in different timezones (server should be timezone-agnostic since everything is UTC — confirm no client-local-time leakage causes incorrect message ordering in the UI).
- **TC-2617** Two messages sent in the *same millisecond* by different users to the same conversation — ordering tiebreak is deterministic (e.g. falls back to `message_id`/insertion order), not flaky between test runs.
- **TC-2618** File size exactly at the upload boundary (1 byte under the limit → accepted; exactly at the limit → accepted or rejected, confirm which; 1 byte over → `413`).
- **TC-2619** Zero-byte file upload (empty file selected) — rejected cleanly, not stored as a broken 0-byte "photo".

### 26.3 Concurrency & race conditions

- **TC-2620** Two devices logged in as the same user both attempt to refresh using two *different but both currently-valid* refresh tokens (e.g. one issued at signup, one from a later login) simultaneously — both should succeed independently (multi-session), verify one refresh rotating doesn't invalidate the other device's unrelated session.
- **TC-2621** User sends a message to peer X in the same instant peer X blocks them — verify a consistent outcome (either the message goes through because the block hadn't committed yet, or it's rejected — no partial state where the message is persisted but delivery/push both silently fail).
- **TC-2622** Admin changes a user's status to `banned` in the same instant that user is mid-request (e.g. uploading a photo) — the in-flight request completes based on whichever status was read at query time; verify no crash from a state change mid-transaction.
- **TC-2623** Two admins simultaneously delete the same user — one succeeds (`204`), the other gets `404` (not a `500` from a double-delete race).
- **TC-2624** Rapid double-tap on "send message" in the mobile UI before the first request's response returns — verify no duplicate message is sent (debounce/disable-while-pending on the send button), separate from the optimistic-ID-collision issue already tracked (TC-1906).
- **TC-2625** Rapid double-tap on "upload main photo" — verify only one upload proceeds, or both proceed safely without corrupting `photo_url` (last-write-wins is fine, but no crash/orphaned temp file).
- **TC-2626** User logs out on Device A while Device B (same account) has an in-flight API request using a refresh token that Device A's logout just revoked — Device B's request fails cleanly with `401`, not a hang or crash, and Device B's own subsequent refresh attempt correctly routes to re-login.

### 26.4 Network, device, and environment edge cases

- **TC-2627 [MOB]** Photo upload interrupted mid-transfer (app backgrounded, wifi drops) — no partial/corrupt file left in `/uploads`, and the client shows a retry option rather than a silently "stuck" spinner.
- **TC-2628 [MOB]** Device with very low free storage during photo pick/resize (`resizePhoto`) — `ImageManipulator` failure is caught (already tracked as TC-710) with a specific check for the low-storage error path.
- **TC-2629 [MOB]** Push notification received while the app is in the foreground vs. background vs. fully killed — each state routes the tap to the correct chat screen (deep link handling).
- **TC-2630 [MOB]** OS-level notification permission denied — app doesn't crash on `registerPushToken`, and the user isn't blocked from using chat, just doesn't get push delivery.
- **TC-2631 [MOB]** Device clock set significantly wrong (user manually changes system time) — token expiry checks and message timestamps behave sanely rather than causing spurious "session expired" loops.
- **TC-2632 [WEB/ADM]** Browser back/forward button navigation through authenticated pages after logout — doesn't show cached authenticated content from the bfcache; hitting back after logout redirects to login rather than showing a stale page.
- **TC-2633 [WEB/ADM]** Opening the same account in two browser tabs — logging out in one tab is reflected in the other on its next API call (via the 401 → refresh-fails → redirect path), not left in a zombie authenticated-looking state.
- **TC-2634 [MOB]** App update/reinstall: an old, still-valid refresh token persisted via SecureStore survives an app update — verify no breaking changes to token format/claims would strand existing logged-in users after a deploy.
- **TC-2635** Slow-network simulation (high latency, e.g. 3G throttling) on every "spinner-then-content" screen — loading states don't flash-and-disappear in a jarring way, and no request fires twice due to an impatient user retrying while the first is still pending.
- **TC-2636** Server-side request timeout / connection drop mid-response (e.g. large discover-page response cut off) — client shows a network error, not a JSON-parse crash on a truncated body.

### 26.5 Malicious/adversarial input (beyond the auth-specific SEC cases)

- **TC-2637** HTML/script injection in `name`, `bio`, `city`, or chat `content` (e.g. `<script>alert(1)</script>`, `<img src=x onerror=...>`) — verify web/admin render this as inert text (React's default escaping) rather than executing it; explicitly check any place that might use `dangerouslySetInnerHTML` or similar.
- **TC-2638** SQL `LIKE` wildcard injection in admin `search` (`%`, `_` characters) — a search for `%` shouldn't return the entire user table as an unintended "match everything"; verify wildcards are escaped or the behavior is at least understood/documented.
- **TC-2639** Extremely large JSON body on any POST/PUT endpoint (multi-MB payload with legit-looking but huge string fields) — rejected by a body-size limit before it reaches validators, not accepted and processed field-by-field.
- **TC-2640** Malformed multipart/form-data on photo upload endpoints (missing boundary, truncated multipart body) — clean `4xx`, not a hung request or crash.
- **TC-2641** Replaying a captured, still-valid JWT from a different IP/device than it was issued on — currently unbound to IP/device (expected for a mobile app with changing IPs), confirm this is an accepted tradeoff rather than an oversight.
- **TC-2642** Header injection via `Authorization` (CRLF sequences, oversized header) — handled by the HTTP layer, not passed through to logs unsanitized (log-injection check, ties to the "no structured logging" finding in improve.md).
- **TC-2643** Uploading an image file crafted to exploit a known image-library vulnerability (e.g. malformed EXIF, decompression bomb — a tiny file that expands to gigabytes on decode) — verify `sharp`/whatever image processing library is used has size/memory guards.

### 26.6 State-transition and lifecycle edge cases

- **TC-2644** User with zero photos and an empty bio appears in another user's discover feed — UI (mobile/web) shows a sensible placeholder rather than a broken/blank card.
- **TC-2645** User deletes their last remaining additional photo, then their main photo, ending up with zero photos entirely while account is still active — profile screens and peer-facing views degrade gracefully.
- **TC-2646** Conversation where the peer has since been deleted by an admin — `ChatHistoryScreen`/`ChatHistoryPage` entry for that thread doesn't crash when rendering a peer whose profile lookup now 404s (ties to TC-1510/TC-2304, but specifically from the list-view rendering angle, not just "does the server crash").
- **TC-2647** A user blocks, then the *same* peer's account is later deleted by an admin — no orphaned `user_blocks` row causes an error on subsequent discover queries (cascade should clean this up per TC-1802, but verify the discover query itself is resilient even if it weren't).
- **TC-2648** Freshly signed-up user (empty profile) immediately hits `GET /users/discover` before completing their profile — doesn't error, and correctly still excludes themselves from their own results even with a blank `name`.
- **TC-2649** Admin promotes/demotes `is_admin` — there is no visible endpoint for this in the current route list (`is_admin` isn't part of the `PUT /admin/users/:id/status` payload); confirm how admin accounts are actually provisioned today (direct DB seed?) and whether that gap is intentional.
- **TC-2650** Session cleanup: a user with many old, expired-but-never-deleted `user_sessions` rows (refresh was never called to trigger rotation-cleanup) — verify there's no unbounded growth of stale session rows, or that this is an accepted/expected characteristic rather than a leak.

---

## Suggested test-suite priorities

1. **Write first (security regressions currently failing against the live code):** TC-307, TC-1303 (access/refresh token confusion), TC-1211/TC-1212/TC-1308 (unvalidated self-message / nonexistent-peer crash path, REST *and* WS), TC-604/605 (empty PUT body 500), TC-1803 (multi-migration bug).
2. **Write second (core user journeys, no known bug but high user impact):** sections 1–13 happy-path + boundary cases (signup/login/refresh/profile/photos/discover/block/chat).
3. **Write third (moderation & admin):** sections 14–15, especially self-lockout protections and cascade-delete correctness.
4. **Backfill as fixes land:** every case above tagged as a "regression test for improve.md ___" should be added to CI in the same PR that fixes the underlying issue, so it stays red until the fix lands and then locks in the fix permanently.
