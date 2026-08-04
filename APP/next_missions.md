# Next Missions — Centralized Logic Core (APP/shared)

## Purpose

This is the execution checklist for the "Centralized Logic Core" architecture
agreed on in planning: routing/session flow, validation rules, and
user-facing copy move into `APP/shared`, consumed by web, mobile, and (for
validation/copy) the backend — without merging any UI.

**Status: ALL PHASES COMPLETE** (Tasks 0.1–0.4, 1.1–1.14, 2.1–2.14, 3.1–3.9,
4.1, 5.1–5.3). The Centralized Logic Core migration described in this
document is finished and fully verified.
Work through remaining tasks in order; each is small and independently
verifiable. Do not start a task until the previous one's "Verify after" step
is green.

**Standing rules for every task below:**
- All new/edited code follows **Allman brace style** (`{` on its own line).
- Nothing under `APP/shared` may import React, React Native, `react-router`,
  `@react-navigation`, or reach for `window`/`localStorage`/`SecureStore`.
  Platform state is always passed in (dependency injection), never detected.
- Deep imports only (`@shared/flow/authFlow`), never a barrel file.
- One concept per file, named after its main export.

**Ordering note:** the design conversation numbered testing as "Phase 5,"
but the `APP/tests/shared` Jest runner has to exist *before* Phase 1 can
write a test into it. So the runner setup is pulled forward into Phase 0
here. The rest of Phase 5 (full regression habit, optional cleanup) stays
last, as a wrap-up.

**Known gap found during planning, fixed as part of this work (not before):**
`deriveUsername()` (web + mobile) doesn't enforce the 3-character minimum
the backend requires, so a short email local-part (e.g. `a1@x.com`) can
produce a username that fails backend validation with a confusing message.
Fixed in Phase 2.

---

## Phase 0 — Foundation & Test Infrastructure ✅ COMPLETE

### Task 0.1 — Add `APP/shared/tsconfig.json` ✅ DONE

**What:** `APP/shared` currently has no `tsconfig.json` of its own — it's
only ever typechecked indirectly, through whichever consumer's `@shared/*`
path alias pulls it in. Add a standalone config so shared code can be
typechecked in isolation.

**Files:** `APP/shared/tsconfig.json` (new)

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "noEmit": true
  },
  "include": ["**/*.ts"],
  "exclude": ["node_modules"]
}
```

**Verify before:** `ls APP/shared/*.json` — confirm no `tsconfig.json`
already exists (avoid clobbering something unexpected).

**Verify after:** `cd APP/shared && npx tsc --noEmit` — should pass with
zero errors (currently zero `.ts` files besides `package.json`'s deps
exist to typecheck against, so this is really "the config itself is
valid").

---

### Task 0.2 — Add Jest + ts-jest to `APP/shared`, create its Jest config ✅ DONE

**What:** Give `APP/shared` its own test runner rather than borrowing
backend's, matching the "shared is an independent package" principle.
Mirrors the existing `APP/backend/jest.config.js` pattern (roots pointed
at the relocated `APP/tests/...` folder).

**Steps:**
1. `cd APP/shared && npm install --save-dev jest ts-jest typescript @types/jest`
2. Create `APP/shared/jest.config.js`:
```js
/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: 'node',
  roots: ['<rootDir>/../tests/shared'],
  testTimeout: 10_000,
  verbose: true,
  modulePaths: ['<rootDir>/node_modules'],
  transform: {
    '^.+\\.tsx?$': ['ts-jest', { tsconfig: '<rootDir>/../tests/shared/tsconfig.json' }],
  },
};
```
3. Add `"test": "jest"` to `APP/shared/package.json`'s `scripts`.

**Verify before:** confirm `APP/backend/jest.config.js` still matches the
pattern being mirrored (re-read it — it may have changed since planning).

**Verify after:** `cd APP/shared && npm test` — should run with **0 tests
found** (no test files exist yet) and exit cleanly, not error. A hard
failure here means the config itself is broken, not "no tests yet."

**As actually implemented:** `typescript` must be pinned to `5.6.3`, not
left at latest — `npm install typescript` defaults to `7.x`, which
`ts-jest@29` doesn't support (`peer typescript@">=4.3 <7"`). Also added
`passWithNoTests: true` to `jest.config.js` — Jest's default behavior is to
**fail** on zero matched tests, which contradicts this task's own "clean
exit" expectation until Phase 1 adds the first test file.

---

### Task 0.3 — Create `APP/tests/shared/tsconfig.json` ✅ DONE

**What:** Mirrors `APP/tests/backend/tsconfig.json`'s shape, pointed at
`APP/shared` instead of `APP/backend`.

**Files:** `APP/tests/shared/tsconfig.json` (new)

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "moduleResolution": "node",
    "esModuleInterop": true,
    "skipLibCheck": true,
    "strict": true,
    "isolatedModules": true,
    "baseUrl": "../../shared",
    "typeRoots": ["../../shared/node_modules/@types"],
    "types": ["jest", "node"]
  },
  "include": ["**/*.ts"]
}
```

**Verify before:** confirm `APP/tests/shared/` doesn't already exist.

**Verify after:** re-run Task 0.2's `npm test` — still 0 tests, still
clean exit (confirms the tsconfig reference in `jest.config.js` resolves).

---

### Task 0.4 — Write `APP/shared/README.md` ✅ DONE

**What:** Document the folder layout and the four standing conventions
(deep imports only, framework purity, one-concept-per-file, Allman style)
so they're discoverable without re-deriving them from this file.

**Files:** `APP/shared/README.md` (new)

**Content:** folder tree (`api/`, `types/`, `utils/`, `flow/`,
`validation/`, `copy/` — note `flow/`, `validation/`, `copy/` don't exist
yet until their phases land) + the four conventions, each with a one-line
reason.

**Verify before:** none (purely additive doc file).

**Verify after:** read it back; confirm it accurately describes the
*current* state of `APP/shared` (don't describe `flow/` as existing until
Phase 1 actually creates it).

---

## Phase 1 — Session & Routing Flow ✅ COMPLETE

### Task 1.1 — Remove the stale draft ✅ DONE

**What:** `APP/shared/navigation/authFlow.ts` was an earlier draft that
predates the agreed `flow/` naming and the events/guards split. Delete it
before creating the real file, so there's no confusion between the two.

**Verify before:** `grep -r "shared/navigation" APP/web/src APP/mobile/src
APP/admin/src APP/backend/src` — confirm zero references (nothing was ever
wired to the draft).

**Verify after:** confirm the file and its now-empty parent folder
(`APP/shared/navigation/`) are gone.

---

### Task 1.2 — Create `APP/shared/flow/authFlow.ts` ✅ DONE

**What:** The finalized event/guard rules, agreed in full during planning.

**Files:** `APP/shared/flow/authFlow.ts` (new)

```ts
export type AuthDestination = 'home' | 'login';

export type AuthFlowEvent =
    | 'afterLogin'
    | 'afterSignup'
    | 'afterLogout'
    | 'afterSessionExpired';

export const AUTH_FLOW_EVENTS =
{
    afterLogin:          'home',
    afterSignup:         'login',
    afterLogout:         'login',
    afterSessionExpired: 'login',
} as const satisfies Record<AuthFlowEvent, AuthDestination>;

export type AuthFlowGuard =
    | 'whenAuthenticatedOnAuthScreen'
    | 'whenUnauthenticatedOnProtectedScreen';

export const AUTH_FLOW_GUARDS =
{
    whenAuthenticatedOnAuthScreen:        'home',
    whenUnauthenticatedOnProtectedScreen: 'login',
} as const satisfies Record<AuthFlowGuard, AuthDestination>;
```

**Verify before:** Task 1.1 complete.

**Verify after:** `cd APP/shared && npx tsc --noEmit` — zero errors.

---

### Task 1.3 — Create `APP/tests/shared/flow/authFlow.test.ts` ✅ DONE

**What:** Verify every event and guard maps to a valid `AuthDestination`,
and that the exported key sets match exactly what's expected (catches a
typo'd or accidentally-removed key at test time, not runtime).

**Verify before:** Task 1.2 complete.

**Verify after:** `cd APP/shared && npm test` — new test file runs and
passes; total test count increased by however many cases were written.

---

### Task 1.4 — Create `APP/web/src/auth/destinations.ts` ✅ DONE

**What:** Web's own lookup from `AuthDestination` to an actual route path.

```ts
import type { AuthDestination } from '@shared/flow/authFlow';

export const WEB_DESTINATIONS: Record<AuthDestination, string> =
{
    home:  '/discover',
    login: '/login',
};
```

**Verify before:** confirm `@shared` path alias resolves in
`APP/web/tsconfig.json` / `vite.config.ts` (it already does — used by
`@shared/api/*` today).

**Verify after:** `cd APP/web && npx tsc --noEmit` — zero errors.

---

### Task 1.5 — Wire `APP/web/src/auth/RequireAuth.tsx` ✅ DONE

**What:** Replace the hardcoded `<Navigate to="/login" replace />` with a
lookup: `WEB_DESTINATIONS[AUTH_FLOW_GUARDS.whenUnauthenticatedOnProtectedScreen]`.

**Verify before:** re-read the current file (it may have drifted since
this was last touched) to confirm the exact lines to change.

**Verify after:**
- `cd APP/web && npx tsc --noEmit`
- `cd APP/web && npm test`
- Manual browser check: clear `localStorage`/`sessionStorage`, navigate
  directly to `/discover` and `/profile` — both must still redirect to
  `/login`.

---

### Task 1.6 — Wire `APP/web/src/auth/RedirectIfAuthed.tsx` ✅ DONE

**What:** Replace the hardcoded `<Navigate to="/discover" replace />` with
`WEB_DESTINATIONS[AUTH_FLOW_GUARDS.whenAuthenticatedOnAuthScreen]`.

**Verify after:**
- `npx tsc --noEmit`, `npm test` (web)
- Manual browser check: log in, then navigate directly to `/login` and
  `/signup` — both must still redirect to `/discover`. Repeat the
  back-to-back reload test done during planning (this is exactly the path
  that exposed the StrictMode refresh-token race earlier — re-confirm that
  fix still holds after this change).

---

### Task 1.7 — Wire `APP/web/src/pages/LoginPage.tsx` ✅ DONE

**What:** Replace `navigate('/discover', { replace: true })` with
`navigate(WEB_DESTINATIONS[AUTH_FLOW_EVENTS.afterLogin], { replace: true })`.

**Verify after:** `npx tsc --noEmit`, `npm test`, manual login flow
end-to-end.

---

### Task 1.8 — Wire `APP/web/src/pages/SignupPage.tsx` ✅ DONE

**What:** Replace `navigate('/login', { replace: true })` with
`navigate(WEB_DESTINATIONS[AUTH_FLOW_EVENTS.afterSignup], { replace: true })`.

**Verify after:** `npx tsc --noEmit`, `npm test`, manual signup flow —
register, confirm it lands on `/login` (not auto-authenticated), then log
in with the new credentials.

---

### Task 1.9 — Wire `APP/web/src/pages/ProfilePage.tsx` (logout) ✅ DONE

**What:** Replace `navigate('/login', { replace: true })` in
`handleLogout` with `navigate(WEB_DESTINATIONS[AUTH_FLOW_EVENTS.afterLogout], { replace: true })`.

**Verify after:** `npx tsc --noEmit`, `npm test`, manual logout flow.

---

### Task 1.10 — Full web regression for Phase 1 ✅ DONE

**Verify after:**
- `cd APP/web && npx tsc --noEmit && npm test`
- Manual pass covering all 5 flows in one session: unauthenticated → protected
  route redirect, authenticated → login/signup redirect, login, signup,
  logout.

---

### Task 1.11 — Create `APP/mobile/src/navigation/destinations.ts` ✅ DONE

**What:** Mobile's own lookup from `AuthDestination` to a screen name.

```ts
import type { AuthDestination } from '@shared/flow/authFlow';

export const MOBILE_DESTINATIONS =
{
    home:  'Menu',
    login: 'Login',
} as const satisfies Record<AuthDestination, 'Menu' | 'Login'>;
```

**As actually implemented, this differs from what was originally planned
above** — the plain `Record<AuthDestination, 'Menu' | 'Login'>` annotation
type-checks fine on its own, but widens every lookup to the union
`'Menu' | 'Login'` instead of the specific literal for that key. React
Navigation's `navigate()` requires the exact literal (`'Login'`, not
`'Login' | 'Menu'`), so `MOBILE_DESTINATIONS[AUTH_FLOW_EVENTS.afterSignup]`
failed to typecheck in Task 1.12 until switched to `as const satisfies` —
the same pattern `authFlow.ts` already uses, which preserves each key's
literal type. React Router's `navigate()` on web takes a plain `string`, so
`WEB_DESTINATIONS` (Task 1.4) never hit this.

**Verify before:** confirmed `@shared` did **not** resolve in mobile at
all — no alias existed anywhere (not in `babel.config.js`, not in
`tsconfig.json`, no `metro.config.js`, no workspace). This was wrong in
the original plan, which assumed it already worked like it does on web.
Required setting up the alias from scratch — see below.

**Mobile `@shared` alias setup (new prerequisite, not in the original
plan):**
1. `cd APP/mobile && npm install --save-dev babel-plugin-module-resolver`
2. `APP/mobile/babel.config.js` — add the plugin *before*
   `react-native-reanimated/plugin` (which must stay last):
```js
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: [
      ['module-resolver', { alias: { '@shared': '../shared' } }],
      'react-native-reanimated/plugin',
    ],
  };
};
```
3. `APP/mobile/tsconfig.json` — add matching `paths` (plus
   `ignoreDeprecations: "6.0"`, since bare `baseUrl` is deprecated in the
   TypeScript version this project uses):
```json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true,
    "ignoreDeprecations": "6.0",
    "baseUrl": ".",
    "paths": { "@shared/*": ["../shared/*"] }
  }
}
```
4. **`APP/mobile/metro.config.js` (new file, didn't exist before) — the
   part that's easy to miss.** `tsc` and the babel plugin both resolve the
   alias fine, but Metro's bundler still refused to load the file at
   runtime with `UnableToResolveError`, because Metro doesn't watch or
   resolve anything outside `APP/mobile`'s own root by default, regardless
   of what Babel rewrites the import path to:
```js
const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const projectRoot = __dirname;
const sharedRoot = path.resolve(projectRoot, '..', 'shared');

const config = getDefaultConfig(projectRoot);
config.watchFolders = [sharedRoot];
config.resolver.nodeModulesPaths = [path.resolve(projectRoot, 'node_modules')];

module.exports = config;
```

**Verify after:**
- `cd APP/mobile && npx tsc --noEmit`
- Prove Metro can actually bundle it (tsc alone isn't sufficient — it
  resolves paths independently of the real bundler): start Metro
  (`CI=1 npx expo start --clear`, since no device/simulator is available
  in this environment) and request a real bundle —
  `curl "http://localhost:8081/index.bundle?platform=android&dev=true"`.
  Must return HTTP 200 and the output must contain the shared module's
  exported names (confirms it isn't a stale cached response).

---

### Task 1.12 — Wire `APP/mobile/src/screens/signup/SignupScreen.tsx` ✅ DONE

**What:** Replace `navigation.navigate('Login')` (post-signup) with
`navigation.navigate(MOBILE_DESTINATIONS[AUTH_FLOW_EVENTS.afterSignup])`.

**Verify after:**
- `cd APP/mobile && npx tsc --noEmit && npm test` — 20/20 pass
- No device/simulator available in this environment, so verified via the
  live Metro bundle request described in Task 1.11 instead (confirmed the
  bundle succeeds and contains `MOBILE_DESTINATIONS`/`AUTH_FLOW_EVENTS`) —
  stronger than tsc alone, but still not the same as an on-device manual
  check. Flagging that gap explicitly rather than silently treating it as
  equivalent.

---

### Task 1.13 — Annotate `APP/mobile/src/navigation/RootNavigator.tsx` ✅ DONE

**What:** No logic change — `user ? <MainStack/> : <AuthStack/>` already
satisfies both guard rules structurally. Add a code comment referencing
`AUTH_FLOW_GUARDS` so the connection is documented, not just implicit.

**Verify after:** `npx tsc --noEmit` (comment-only change, should be a
no-op diff in behavior).

---

### Task 1.14 — Phase 1 close-out: full four-package regression ✅ DONE

**Verify after:**
- `npx tsc --noEmit` in `APP/web`, `APP/mobile`, `APP/admin`, `APP/backend`
  — all clean
- `npm test` in `APP/web` (14 pass + 3 expected-fail), `APP/mobile`
  (20/20), `APP/admin` (14/14), `APP/backend` (187/187), `APP/shared`
  (8/8) — all green
- Full manual smoke pass on web via live browser automation, all 5 flows
  confirmed working end-to-end: unauthenticated → protected route
  redirect, authenticated → login/signup redirect, login → home, signup →
  login (no auto-auth), logout → login
- Mobile: no on-device pass (no simulator available); verified via a real
  Metro bundle request instead (see Task 1.11/1.12)

---

## Phase 2 — Validation Rules ✅ COMPLETE

### Task 2.1 — Create `APP/shared/validation/credentials.ts` ✅ DONE

**What:** Username length (3–30) + charset (`/^[a-zA-Z0-9_]+$/`), email
format, password min length (8), and `deriveUsername()` — this version
**fixes** the found gap by padding/rejecting derived usernames under 3
chars instead of silently producing one.

```ts
export type ValidationError = string | null;

export function validatePassword(password: string): ValidationError
{
    if (password.length < 8)
    {
        return 'password_too_short';
    }
    return null;
}

export function validateEmail(email: string): ValidationError
{
    // ... format check, returns 'invalid_email' or null
}

export function validateUsername(username: string): ValidationError
{
    // ... length 3-30 + charset check
}

export function deriveUsername(email: string): string
{
    // ... existing strip/lowercase/slice(0,30) logic,
    // now also guarantees a 3-char minimum
}
```

**Verify before:** re-read the current `deriveUsername` implementations in
`web/SignupPage.tsx` and `mobile/SignupScreen.tsx` to confirm the exact
logic being consolidated hasn't drifted. Confirmed byte-for-byte identical.

**Verify after:** `cd APP/shared && npx tsc --noEmit`. Also confirmed live
end-to-end later (Task 2.10): signed up with `a1@test.com` in a real
browser, derived username `a10`, backend accepted it — a follow-up curl
signup attempt using `a10` directly failed with `username_taken`,
independently confirming the exact derivation.

---

### Task 2.2 — Create `APP/shared/validation/profile.ts` ✅ DONE

**What:** Required-field checks (name, gender, city) and date-of-birth +
age bounds (18–100), using mobile's stricter day-rollover date check
(`parsed.getDate() !== parseInt(dobDay, 10)`) as the canonical
implementation — this closes the gap where web's date validation was
weaker than mobile's.

**Verify before:** re-read both `web/ProfilePage.tsx` and
`mobile/MyProfileScreen.tsx`'s current validation blocks. Confirmed: web
had NO rollover check (`isNaN` only), mobile had it — exactly as planned.

**Verify after:** `npx tsc --noEmit` (shared).

---

### Task 2.3 — Create `APP/tests/shared/validation/credentials.test.ts` ✅ DONE

**What:** Cover: password boundary (7/8 chars), email format edge cases,
username length/charset boundary, and specifically the fixed
`deriveUsername` bug — assert a short local-part (`a1@x.com`) now produces
a username that also passes `validateUsername`.

**Verify after:** `cd APP/shared && npm test` — all pass.

---

### Task 2.4 — Create `APP/tests/shared/validation/profile.test.ts` ✅ DONE

**What:** Cover age boundary (17/18/100/101) and the Feb-30 rollover case
specifically (this is the exact case web was missing).

**As actually implemented:** the naive "same calendar month/day, N years
back" way of constructing the 18- and 100-year boundary test dates is
flaky — `validateDateOfBirth` uses a 365.25-day-year approximation
(unchanged from the original web/mobile logic), and a calendar year
subtracted naively can land on either side of an exact-N.0 boundary
depending on which specific leap years fall inside that span. First run
failed at the 100-year case for exactly this reason. Fixed by constructing
the 18/100 boundary dates by day-count instead (`isoDateDaysAgo(6575)` /
`isoDateDaysAgo(36524)`), landing safely on the accepting side rather than
exactly on the mathematical edge. The 17/101 cases are far enough from any
boundary that simple calendar-year subtraction is fine.

**Verify after:** `npm test` (shared) — 39/39 pass after the fix above.

---

### Task 2.5 — Wire backend: `APP/backend/src/routes/auth.routes.ts` ✅ DONE

**What:** Replace the inline `express-validator` rules for username/email/
password with `.custom()` wrappers around `validateUsername` /
`validateEmail` / `validatePassword` from `@shared/validation/credentials`.

**Verify before:** re-read current `signupRules` (may have shifted line
numbers since the email-before-username reordering done earlier). Also
checked whether backend had any `@shared` wiring at all — **it did not**,
same as mobile's Phase 1 gap. This turned out to be the largest piece of
unplanned work in Phase 2; see below.

**Backend `@shared` setup (new prerequisite, not in the original plan) —
npm/yarn workspaces, scoped to `backend` + `shared` only** (web/mobile/admin
already have their own working mechanisms from Phase 1 and were left
untouched):

1. `APP/package.json` (new, root workspaces manifest):
```json
{
  "name": "yahdav-workspace-root",
  "private": true,
  "workspaces": ["backend", "shared"]
}
```
2. `cd APP && npm install` — creates the
   `APP/node_modules/@yahdav/shared → APP/shared` symlink.
3. `APP/shared/tsconfig.json` — flipped from `noEmit: true` (Phase 0's
   type-check-only config) to a real emit: `module: CommonJS` (backend is
   plain CommonJS Node, not a bundler target), `declaration: true`,
   `outDir: dist`, `rootDir: "."`. Web/mobile are unaffected — their
   bundlers (Vite, Metro) transform the raw `.ts` source directly and never
   invoke this tsconfig.
4. `APP/shared/package.json` — added subpath `exports` (no barrel, matching
   the deep-imports-only convention) and a `build` script:
```json
"scripts": { "test": "jest", "build": "tsc" },
"exports": { "./*": { "types": "./dist/*.d.ts", "default": "./dist/*.js" } }
```
5. `cd APP/shared && npm run build` — must be re-run whenever shared source
   changes, before backend can pick up the update. **Operational note for
   future work:** there's no automated prebuild hook wiring this yet — a
   real gap if this becomes a recurring friction point.
6. `APP/backend/tsconfig.json` — **do not** change `moduleResolution` to
   `"bundler"` to make it understand the `exports` field (tried this first;
   it errors, since `bundler` resolution requires `module` to be
   `"preserve"` or ES2015+, and backend genuinely needs `CommonJS` for its
   real Node/tsc-compiled runtime). Instead added an explicit `paths`
   mapping, which works with *any* `moduleResolution` and doesn't touch
   `rootDir`/`outDir` (so `dist/server.js`'s location is unaffected):
```json
"baseUrl": ".",
"paths": { "@yahdav/shared/*": ["../shared/dist/*"] }
```
   This only matters for `tsc`'s own type-checking — the emitted JS is a
   plain `require("@yahdav/shared/validation/credentials")`, which Node
   resolves at real runtime via the workspace symlink + `exports` field,
   completely independent of what TypeScript's resolution mode believes.
7. Added `.custom()` wrappers in `signupRules` around `validateUsername` /
   `validateEmail` / `validatePassword`, mapping each returned error code to
   the exact same Hebrew message the inline `express-validator` rules used
   before — no user-visible behavior change.

**Verify after:** verified across all three ways this code actually runs,
not just `tsc`:
- `cd APP/backend && npx tsc --noEmit` — clean
- `npm test -- --testPathPattern=auth` — 46/46 pass (via `ts-jest`'s
  runtime transform)
- **Real production path**: `npm run build` (`tsc`, not `--noEmit`) then
  `node dist/server.js` directly (no `tsx`, no `ts-jest`) — booted past
  migrations and WebSocket setup before hitting an unrelated `EADDRINUSE`
  (a leftover dev server on the same port), proving the compiled
  `require("@yahdav/shared/...")` resolves correctly at real Node runtime.
  A resolution failure would have crashed immediately with
  `MODULE_NOT_FOUND` before reaching that point.

---

### Task 2.6 — Wire backend: profile validation ✅ DONE

**What:** If profile update validation exists server-side (check
`APP/backend/src/routes/profile.routes.ts`), wire it to
`@shared/validation/profile` the same way.

**Verify before:** read `profile.routes.ts` to confirm what validation
currently exists there. Found: `name`/`bio`/`city`/`region`'s max-length
checks aren't things `@shared/validation/profile` covers at all (that
module has no concept of max-length), so those were left untouched. The
real, meaningful gap: `date_of_birth` was only checked against a
`/^\d{4}-\d{2}-\d{2}$/` **format** regex — age bounds and date-rollover
were **never validated server-side at all**. Anyone bypassing the client
could submit any date matching that format, including an impossible one
like `2024-02-30`. Wired `validateDateOfBirth` in as a `.custom()` step
chained after the existing regex (kept as a `.bail()`-guarded pre-check, so
the format-error message stays unchanged for malformed input).

**Verify after:** `npx tsc --noEmit`, `npm test -- --testPathPattern=profile`
(backend) — 50/50 pass. Checked existing test fixtures first
(`TC-609`/`TC-609b`) to confirm none used a date that would newly fail —
`'1995-06-15'` is ~31 years old, well inside bounds.

---

### Task 2.7 — Backend full regression ✅ DONE

**Verify after:** `cd APP/backend && npx tsc --noEmit && npm test` — 187/187,
zero regressions. Also re-ran `npm run build` — production build still
compiles clean after the profile.routes.ts change too.

---

### Task 2.8 — Wire `APP/web/src/pages/SignupPage.tsx` ✅ DONE

**What:** Replace the local `deriveUsername()` and inline password checks
with calls to `@shared/validation/credentials`.

**Verify after:** `npx tsc --noEmit`, `npm test` (web) — clean; manual
signup flow including the short-email edge case deferred to Task 2.10's
consolidated pass (same batching approach used in Phase 1).

---

### Task 2.9 — Wire `APP/web/src/pages/ProfilePage.tsx` ✅ DONE

**What:** Replace local `MIN_AGE`/`MAX_AGE` constants and inline date
validation with `@shared/validation/profile`.

**Verify after:** `npx tsc --noEmit`, `npm test` (web) — clean; manual
check deferred to Task 2.10.

---

### Task 2.10 — Web full regression ✅ DONE

**Verify after:** `cd APP/web && npx tsc --noEmit && npm test` — clean.
Manual browser pass:
- Signed up with `a1@test.com` — succeeded, landed on `/login` (not
  auto-authenticated), no confusing "username" error. Logged in with the
  same credentials afterward — succeeded.
- Attempted the Feb-30 edge case on `/profile`'s date field — **the native
  `<input type="date">` widget itself refuses to ever hold that value** (it
  clamped to empty when set programmatically), so this specific case was
  never reachable through web's actual UI to begin with, only via a direct
  API call or mobile's day/month/year dropdowns. Already fully covered by
  the shared unit tests and the backend API-level tests instead. Completed
  a normal profile save with a valid date to confirm the regular flow
  still works — succeeded ("הפרופיל עודכן בהצלחה").
- Hit one unrelated pre-existing rough edge along the way: submitting an
  empty `region` fails backend's `isLength({min:1})` check even though
  region isn't required client-side — not a regression from this work,
  didn't touch it.

---

### Task 2.11 — Wire `APP/mobile/src/screens/signup/SignupScreen.tsx` ✅ DONE

**What:** Same swap as Task 2.8, mobile side.

**Verify after:** `npx tsc --noEmit`, `npm test` (mobile) — 20/20 pass.

---

### Task 2.12 — Wire `APP/mobile/src/screens/profile/MyProfileScreen.tsx` ✅ DONE

**What:** Same swap as Task 2.9, mobile side — mobile's own stricter date
check becomes a call into the now-shared canonical version instead of
inline logic.

**Verify after:** `npx tsc --noEmit`, `npm test` (mobile) — 20/20 pass.

---

### Task 2.13 — Mobile full regression ✅ DONE

**Verify after:** `cd APP/mobile && npx tsc --noEmit && npm test` — clean,
20/20. Also re-verified the Metro bundle end-to-end (same rigor as Phase
1, since two more mobile files now import shared code): fresh
`CI=1 npx expo start --clear`, requested the real bundle via curl — HTTP
200, and the new validation code (`deriveUsername`, `validatePassword`,
`validateDateOfBirth`, etc.) is present in the output.

---

### Task 2.14 — Phase 2 close-out: full four-package + shared regression ✅ DONE

**Verify after:**
- `npx tsc --noEmit` in all 5 packages — all clean
- `npm test` in all 5 — web (14+3 expected-fail), mobile (20/20), admin
  (14/14), backend (187/187), shared (39/39)
- Manual smoke test covered under Task 2.10 (web) and Task 2.13 (mobile)

**Process note, not architecture:** made the same directory mistake four
separate times during this phase — running a verification command without
an explicit `cd`, so it silently re-ran in whatever the previous command's
directory happened to be instead of the intended package. Every case was
caught by checking the actual output (wrong package name / wrong test
count) and redone correctly, so nothing shipped unverified — but flagging
the pattern here since it's worth being deliberate about in any future
phase: always prefix verification commands with an explicit `cd`, never
rely on assumed persisted shell state, especially across parallel-batched
tool calls.

---

## Phase 3 — User-Facing Copy (i18n) ✅ COMPLETE

### Task 3.1 — Create `APP/shared/copy/client/locales/he.ts` ✅ DONE

**What:** Every Hebrew string currently hardcoded client-side for
validation, keyed by the codes `@shared/validation` produces.

**Verify before:** grep both `APP/web/src` and `APP/mobile/src` for
hardcoded Hebrew validation strings to make sure the dictionary is
complete before wiring anything to it.

**As actually implemented, the real key set differs from the example list
sketched during planning** (`password_too_short`, `passwords_dont_match`,
`invalid_email`, `missing_required_field`, `invalid_date`, `age_too_young`,
`age_too_old`) — grepping the real `setError`/`setValidationError` call
sites showed:
- `invalid_email`/`username_invalid_*` are never rendered from a hardcoded
  client string at all — email format is only checked server-side, and
  there's no username field in the UI. No client key needed for these.
- `missing_required_field` doesn't match current UI behavior — profile
  forms show **field-specific** messages (`שם מלא הוא שדה חובה`, `עיר היא
  שדה חובה`, ...), not one generic message. Used distinct keys
  (`name_required`, `gender_required`, `date_of_birth_required`,
  `city_required`) instead, to keep messages unchanged.
- Signup/login forms show a *different*, more generic message
  (`יש למלא את כל השדות`) for "any field empty" — added as
  `missing_all_fields`, a separate key from the field-specific ones above.
- Found and added `network_error` (the catch-all `שגיאת רשת, נסה שוב`),
  which wasn't in the sketch but is hardcoded in all four
  login/signup screens.

**Two small, deliberate wording unifications** (flagging since they're
user-visible text changes, even though trivial): mobile's profile screen
said `יש למלא תאריך לידה מלא` where web said `יש למלא תאריך לידה` — unified
to web's shorter version under `date_of_birth_required`. Mobile's signup
screen said `שגיאת רשת, נסה שנית` where everywhere else said
`שגיאת רשת, נסה שוב` — unified to the majority wording under
`network_error`. Both are exactly the kind of drift this phase exists to
eliminate.

**Verify after:** `cd APP/shared && npx tsc --noEmit`.

---

### Task 3.2 — Create `APP/shared/copy/client/index.ts` ✅ DONE

**What:** The `LOCALES` map, `ACTIVE_LOCALE` line, and `clientMessage(key)`
resolver, as designed during planning. `clientMessage` takes the strict
`ClientMessageKey` union (not a bare `string`) — safe because every call
site is new code written in Tasks 3.7/3.8, not a pre-existing loose caller.

**Verify after:** `npx tsc --noEmit` (shared).

---

### Task 3.3 — Create `APP/shared/copy/server/locales/he.ts` ✅ DONE

**What:** Move the backend's existing `ERROR_MESSAGES` map (in
`APP/backend/src/utils/responses.ts`) here verbatim — same keys, same
Hebrew text, just relocated.

**Verify before:** re-read `responses.ts`'s current `ERROR_MESSAGES` in
full to copy it exactly, not from memory. Confirmed unchanged from
planning, all 20 keys copied verbatim.

**Verify after:** `npx tsc --noEmit` (shared).

---

### Task 3.4 — Create `APP/shared/copy/server/index.ts` ✅ DONE

**What:** Same shape as `copy/client/index.ts` — own `LOCALES`, own
`ACTIVE_LOCALE`, own `serverMessage(key)`. Unlike `clientMessage`,
`serverMessage` takes a bare `string` with a fallback message for unknown
codes — this has to match backend's existing `errorMessage(code: string)`
signature, which callers can invoke with any string, by design (graceful
degradation for an unrecognized error code).

**Verify after:** `npx tsc --noEmit` (shared).

---

### Task 3.5 — Create `APP/tests/shared/copy/client.test.ts` and `server.test.ts` ✅ DONE

**What:** Assert every key producible by `@shared/validation` has a
matching `client` dictionary entry, and every code used by
`fail(res, code)` call sites in the backend has a matching `server`
dictionary entry (a completeness check).

**Verify before (server dictionary):** grepped every literal
`fail(res, '...')` call site across `src/` (18 distinct codes), plus
checked for dynamic `fail(res, msg)` calls the literal-string grep would
miss — found two (`session_not_found`/`session_expired`, thrown by
`SessionModel` and re-passed in `auth.routes.ts`'s `/refresh` handler).
All 20 dictionary keys confirmed genuinely used, none dead.

**Verify after:** `cd APP/shared && npm test` — 45/45 pass.

---

### Task 3.6 — Wire backend: `APP/backend/src/utils/responses.ts` ✅ DONE

**What:** `errorMessage(code)` delegates to `serverMessage(code)` from
`@shared/copy/server` instead of its own local `ERROR_MESSAGES` map. This
is the highest-blast-radius change in this phase — every `fail()` call in
the entire backend routes through this function.

**Verify before:** confirmed Task 3.3's copied dictionary is byte-for-byte
identical to the original before deleting it.

**A real bug found here, not in the original plan:** `package.json`'s
`exports` wildcard (`"./*": "./dist/*.js"`) does a literal string
substitution with no automatic `/index.js` fallback for directories.
`copy/client` and `copy/server` are directory+`index.ts` modules (unlike
the flat `validation/credentials.ts`), so `@yahdav/shared/copy/server`
resolved to the non-existent `dist/copy/server.js` instead of the real
`dist/copy/server/index.js`. `tsc`'s `paths`-based resolution is smart
enough to find directory-index files on its own, so `tsc --noEmit` passed
clean and gave no warning — the bug only surfaced when Jest's *real*
`require()` failed at actual test-run time. Fixed by adding explicit,
non-wildcard `exports` entries for `./copy/client` and `./copy/server`
ahead of the wildcard fallback (which still covers every flat-file module).
Also had to rebuild `APP/shared`'s `dist/` (stale since Phase 2, before
`copy/` existed) before backend could pick up any of Phase 3's new files
at all — the same "must rebuild after shared source changes" operational
gap flagged in Task 2.5.

**Verify after:** verified all three ways again, matching Task 2.5's rigor:
- `cd APP/backend && npx tsc --noEmit` — clean
- `npm test` — **full suite**, 187/187 (not just auth — this touches every
  route file since every `fail()` call routes through this function)
- Real production path: `npm run build` then `node dist/server.js` — booted
  and actually served a live request; `curl`'d `/auth/login` with bad
  credentials and got back the correct `שם משתמש או סיסמה שגויים`,
  end-to-end through the real compiled server.

---

### Task 3.7 — Wire `APP/web/src` validation-error display sites ✅ DONE

**What:** Everywhere a hardcoded Hebrew validation string is currently set
via `setError(...)`/`setValidationError(...)` (LoginPage, SignupPage,
ProfilePage), replace with `clientMessage(code)`.

**Verify before:** grep for the exact hardcoded strings identified in Task
3.1 to get a complete site list.

**Verify after:** `npx tsc --noEmit`, `npm test` (web) — clean; manual
visual pass deferred to Task 3.9's consolidated check (same batching
approach used in prior phases).

---

### Task 3.8 — Wire `APP/mobile/src` validation-error display sites ✅ DONE

**What:** Same swap, mobile side (SignupScreen, LoginScreen,
MyProfileScreen) — including the two wording unifications from Task 3.1.

**Verify after:** `npx tsc --noEmit`, `npm test` (mobile) — 20/20 pass.

---

### Task 3.9 — Phase 3 close-out: full regression ✅ DONE

**Verify after:**
- `npx tsc --noEmit` in all 5 packages — all clean
- `npm test` in all 5 — web (14+3 expected-fail), mobile (20/20), admin
  (14/14), backend (187/187), shared (45/45)
- Manual browser pass on web: re-triggered `missing_all_fields` (login,
  empty fields), `passwords_dont_match` (signup), and the server-sourced
  `invalid_credentials` message (wrong password) — all rendered the exact
  correct Hebrew text. Completed a full signup → login flow to confirm the
  overall path still works with the copy layer wired in throughout.
- Mobile: verified via a fresh Metro bundle request (same as Phases 1–2) —
  HTTP 200, bundle contains the new client copy code.

---

## Phase 4 — Platform Capability Boundaries ✅ COMPLETE

### Task 4.1 — Append the convention to `APP/shared/README.md` ✅ DONE

**What:** Document: "shared code never detects platform or device
capability itself (no `Platform.OS`, no `expo-*` imports); it only accepts
what it needs as a parameter, via the same dependency-injection pattern as
`createAuthApi(client)`." No code changes.

**Verify before:** re-ran the grep despite the plan saying "none" —
Phases 1–3 added real code to `APP/shared` since this check was last done
in planning, worth confirming nothing new violated it. Still zero matches.

**As actually implemented:** promoted this from a clause buried inside the
"Framework purity" convention (written back in Phase 0) into its own
explicit, numbered convention, and refreshed the README's structure
section — it was stale, still listing `flow/`, `validation/`, and `copy/`
as "planned, not yet created" even though all three landed in Phases 1–3.
Also documented the backend's npm-workspaces consumption model and the
`exports`-wildcard directory-index gotcha from Task 3.6 directly in the
README, since a future contributor adding a new `shared` subpath needs to
know about it before hitting the same Jest-only-not-tsc failure.

**Verify after:** re-ran `grep -rn "Platform.OS\|expo-notifications"
APP/shared APP/web/src` (via the Grep tool, not raw shell `grep`, which
hung scanning `APP/shared/node_modules` — worth remembering for next time)
— confirmed still zero matches.

---

## Phase 5 — Verification & Testing Strategy (wrap-up) ✅ COMPLETE

### Task 5.1 — Completeness audit of `APP/tests/shared` ✅ DONE

**What:** Confirm every module created in Phases 1–3 has a corresponding
test file, per the structure agreed during planning:
```
APP/tests/shared/
    flow/authFlow.test.ts
    validation/credentials.test.ts
    validation/profile.test.ts
    copy/client.test.ts
    copy/server.test.ts
```

**Verify after:** confirmed all 5 files exist exactly as listed (`find
APP/tests/shared -name "*.ts"`), then `cd APP/shared && npm test` — 5/5
suites, 45/45 tests, all green (before Task 5.2 added a 6th).

---

### Task 5.2 — (Optional) Consolidate duplicate `formatDate.test.ts` ✅ DONE (full fix, user's choice)

**What was assumed in the plan:** `formatDate.test.ts` exists separately in
both `APP/tests/web` and `APP/tests/mobile`, testing the same
already-shared `formatDate` util — a simple test-file move.

**What was actually true, found before touching anything:** `formatDate`
was never actually centralized. Web imports the real
`@shared/utils/formatDate`. Mobile had its own **separate local fork**
(`mobile/src/utils/formatDate.ts`), used by `ChatScreen.tsx` and
`ChatHistoryScreen.tsx` — and the fork had **already independently fixed a
bug** the shared version still had: `formatMessageTime`/
`formatConversationTime` had no `isNaN` guard, so `date-fns`' `format()`
would throw a `RangeError` on an invalid/malformed timestamp instead of
returning `''`. Web's own test suite had been silently tracking this as a
known bug via three `it.fails(...)` tests (with a comment explaining the
gap) rather than it ever getting fixed. Naively moving one test file
as originally planned would have either erased mobile's coverage of its
own still-in-use, safer implementation, or papered over a real bug — so
this was flagged and the user chose the full fix over the two lighter
options (skip entirely / just patch the bug and leave the fork in place).

**Full fix applied:**
1. `APP/shared/utils/formatDate.ts` — adopted mobile's safer
   implementation verbatim: `isNaN` guard added to both functions, and
   `formatConversationTime`'s `diffMs < 60_000` check moved to an early
   top-level return (matching mobile's simpler structure) instead of being
   nested inside the `isToday` branch.
2. `APP/mobile/src/screens/chat/ChatScreen.tsx` and `ChatHistoryScreen.tsx`
   — import switched from the local `../../utils/formatDate` to
   `@shared/utils/formatDate`.
3. `APP/mobile/src/utils/formatDate.ts` — deleted, after confirming zero
   remaining references.
4. `APP/tests/shared/utils/formatDate.test.ts` (new) — genuinely
   consolidated: web's three former `it.fails` tests are now normal
   passing tests (the bug is fixed), plus mobile's extra "earlier today
   but over a minute old" case, which exercised `formatDistanceToNow`
   specifically and wasn't in web's suite at all.
5. `APP/tests/web/formatDate.test.ts` and `APP/tests/mobile/formatDate.test.ts`
   — deleted.

**Verify after:**
- `cd APP/shared && npx tsc --noEmit && npm test` — 55/55 pass (6 suites,
  up from 45/5 — the 10 new consolidated formatDate tests)
- `cd APP/web && npx tsc --noEmit && npm test` — 8/8 pass (down from
  14+3-expected-fail; the 3 expected-fail tests are gone because they were
  exactly the bug-tracking tests for the bug just fixed)
- `cd APP/mobile && npx tsc --noEmit && npm test` — 10/10 pass (down from
  20/20, minus the 10 tests that moved to shared)
- Mobile Metro bundle re-verified (fresh cache, real HTTP request) since
  two screen files' import paths changed — HTTP 200, bundle contains
  `formatMessageTime`/`formatConversationTime`
- Confirmed `APP/backend/src` never imports `formatDate` at all — no
  `dist/` rebuild needed for this specific change

---

### Task 5.3 — Final full-repo regression ✅ DONE

**Verify after:**
- `npx tsc --noEmit` in all 5 packages — all clean
- `npm test` in all five packages — web (8/8, the 3 expected-fail baseline
  is gone since Task 5.2 fixed the bug they tracked), mobile (10/10),
  admin (14/14), backend (187/187), shared (55/55)
- Full manual smoke pass on web, live in browser, all 6 flows in one
  session: unauthenticated → protected route redirect, authenticated →
  login/signup redirect, signup (fresh account), login, profile save,
  logout. All confirmed working end-to-end.
- Mobile: no on-device pass available in this environment (no simulator).
  Best-effort verification throughout the whole plan was the repeated
  Metro bundle checks (Phases 1–3 and Task 5.2's formatDate
  consolidation) — each confirmed a real HTTP 200 bundle response
  containing the relevant shared code, the strongest verification
  possible without a device.

**This closes out the entire `next_missions.md` plan.** The Centralized
Logic Core (`APP/shared/{flow,validation,copy}`) is built, tested, wired
into web/mobile/backend, and documented.
