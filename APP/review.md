# Mobile ↔ Web Code Sharing Audit

**Scope:** `APP/mobile/src` (55 files, ~3,252 lines) vs. `APP/web/src` (32 files,
~2,581 lines), evaluated against the existing `APP/shared` package (24 files,
~714 lines). Backend and admin panel are out of scope except where they
already consume `shared`.

**Method:** manual pairwise comparison of every mobile screen/hook against its
web page/component counterpart, plus the auth, API-client, and utility
layers. No code was written or modified — findings only.

---

## 1. Executive Summary

- **This codebase already has a shared package, and it's well designed.**
  `APP/shared` exists, has clear conventions (deep imports only, no React,
  no platform detection, one concept per file), and is enforced in places by
  real tests (e.g. `theme/colors.test.ts`) and by the compiler (`pageIds.ts`
  + `satisfies Record<PageId, string>`). The architecture concept is sound —
  this audit is about applying it more completely, not inventing it.

- **The single biggest finding is migration debt, not missing abstraction.**
  `@shared/api/auth.ts`, `@shared/api/users.ts`, and `@shared/api/chat.ts`
  already exist as framework-agnostic Axios-client factories. **Web already
  consumes them.** Mobile does not — `mobile/src/api/axios.ts`,
  `api/chat.ts`, and `api/users.ts` are hand-rolled duplicates of code that
  already lives in `shared` and is already proven in production on web. This
  alone accounts for roughly a third of the duplication found below, and
  fixing it is closer to an import swap than a redesign.

- **Estimated duplication level: ~15% of raw source lines, ~30–35% of
  non-JSX business logic.** Raw-line duplication looks moderate because
  screens/pages are dominated by platform-specific JSX/StyleSheet markup
  that genuinely can't be shared. But strip the markup away and a
  meaningful share of the *logic* underneath — validation ordering, pure
  formatters, pagination bookkeeping, domain constants — is copy-pasted
  between a `.tsx` screen and its `.tsx` page almost verbatim, usually with
  the exact same Hebrew error strings.

- **Overall sharing potential: high for logic, low for presentation.**
  Nothing found below argues for sharing components or layout — React
  Native's View/StyleSheet and web's div/Tailwind are different enough that
  attempting a shared UI layer would be the over-engineering trap. The
  opportunity is entirely in pure functions, validation chains, domain
  constants, and API/session plumbing, which is exactly the shape
  `APP/shared` was already built for.

- **Organizational pattern observed:** every duplicate found follows the
  same shape — a `mobile/src/hooks/useX.ts` paired with logic inlined
  directly inside a `web/src/pages/XPage.tsx` (web has no hooks folder; its
  pages own their state directly). The duplication isn't mobile-vs-mobile or
  web-vs-web, it's the same business rule expressed twice, once per
  platform's state-management style.

---

## 2. Sharing Opportunities

### 🔴 Level 5 — CRITICAL (Must Share)

#### 2.1 API client refresh/interceptor logic
- **Code Section:** `mobile/src/api/axios.ts` (85 lines) vs.
  `web/src/api/client.ts:1-111` — request interceptor, response interceptor,
  `performRefresh()` in-flight-dedup logic, and the
  `data.success === false && data.error === 'unauthorized'` detection rule.
- **Affected Apps:** All authenticated mobile API calls; all authenticated
  web API calls.
- **Similarity:** Near line-for-line identical, including the comment
  explaining *why* (backend always returns HTTP 200, refresh tokens are
  single-use, StrictMode double-invoke race). The comments were clearly
  copy-pasted and edited, which is itself a signal this was written twice by
  the same author who understood it was the same logic.
- **Business Logic Rationale:** This is the app's entire auth-refresh
  correctness guarantee. Two independent implementations means two places a
  future auth bug can be fixed in one and not the other — this is the
  highest-risk duplication in the codebase precisely because it's security/
  session-integrity code.
- **Implementation Notes:** `webTokenStorage` (sessionStorage/localStorage)
  and mobile's `storage.ts` (SecureStore + in-memory cache) already share
  the same shape (`getAccessToken`/`getRefreshToken`/clear). A
  `createApiClient(baseURL, tokenStorage, onAuthFailure)` factory in
  `shared/api/` — taking the storage adapter as a parameter per Convention 2
  — could produce the configured Axios instance for both platforms. Web's
  version additionally does `window.location.href = '/login'` on failed
  refresh where mobile calls `onAuthFailure?.()`; that's exactly the kind of
  platform decision that should stay a caller-supplied callback, not branch
  inside shared code.
- **Estimated Impact:** ~85 lines removed from mobile, ~70 lines removed
  from web, net one ~90-line shared implementation. Maintenance reduction:
  high — this logic changes rarely but is catastrophic to get wrong.
  **Risk: Low** (behavior is already proven identical in both; extraction is
  mechanical).

> ✅ **DONE** — 2026-08-06
> **What changed:** New `shared/api/client.ts` exports
> `createApiClient(baseURL, tokenStorage, onAuthFailure)`, taking a small
> `ApiTokenStorage` interface (DI, per Convention 2) covering
> `getAccessToken`/`getRefreshToken`/`applyRefreshedTokens`/`clear`, and
> returning `{ client, performRefresh }`. `mobile/src/api/axios.ts` (85 →
> ~25 lines) and `web/src/api/client.ts` (111 → ~35 lines) are now thin
> wrappers supplying their platform's token storage and auth-failure
> behavior. No consumer-facing names changed: `api`, `setOnAuthFailure`,
> `axiosClient`, `performRefresh`, `authApi`/`usersApi`/`chatApi` all still
> exist with the same shapes; `AuthContext.tsx` on both platforms is
> untouched.
> **Tests-first (Rule 1):** wrote 5 pinning tests in
> `APP/tests/shared/api/client.test.ts` against a local reference
> implementation of the single-flight dedup pattern (transcribed from both
> platforms' then-unmodified `performRefresh`), covering the concurrent-
> refresh race specifically — dedup to one call, correct guard reset on
> success/failure/exception, no stale-result reuse. Confirmed 5/5 passing,
> got explicit approval, implemented `createApiClient`, added 2 more tests
> (no-token short-circuit, `applyRefreshedTokens` call verification) for a
> total of 7, all passing against the real export.
> **Deviations from the report — two flagged and resolved during
> implementation, not decided silently:**
> 1. **Refresh-call transport.** Mobile's original interceptor used a raw
>    `axios.post(...)` for the `/auth/refresh` call itself (bypassing the
>    wired client, structurally immune to recursion); web used
>    `axiosClient.post(...)` (the interceptor-wired instance). Standardized
>    on mobile's raw-`axios.post` approach per your explicit instruction to
>    "stick to the architecture" after this was surfaced.
> 2. **A pre-existing test suite I hadn't discovered during planning** —
>    `APP/tests/web/client.test.ts` (8 tests, using `axios-mock-adapter`
>    mounted on `axiosClient`) — broke as a direct consequence of decision
>    #1, because its mock adapter can't see calls made via raw `axios.post`.
>    Fixed by mounting a second `MockAdapter` on the global `axios` module
>    specifically for the `/auth/refresh` call (matched by `RegExp` since
>    the raw call uses a full absolute URL, not `axiosClient`'s
>    baseURL-relative path), with `afterAll(() => refreshMock.restore())`
>    so the global-axios mock can't leak into other test files. Required
>    adding an `axios` alias to `web/vitest.config.ts` (mirroring the
>    existing `axios-mock-adapter` alias) since the test file now imports
>    `axios` directly and lives outside `APP/web/`'s own `node_modules`
>    resolution path. All 8 of that file's tests — including its own
>    concurrent-refresh-race test and a regression test for a real deadlock
>    bug from an earlier interceptor design — pass unchanged in substance
>    against the new implementation.
> 3. Fixed one test-timing assumption in the new pinning suite itself (not
>    a behavior change): the real `createApiClient` awaits
>    `tokenStorage.getRefreshToken()` before calling `axios.post` (needed
>    since mobile's version is genuinely async via SecureStore), one
>    microtask tick later than my simplified reference implementation
>    assumed — fixed with an `await Promise.resolve();` before the interim
>    assertion; final assertions were unaffected and confirmed with you
>    before applying.
> **Tests:** `APP/tests/shared/api/client.test.ts` (7 tests, new) +
> `APP/tests/web/client.test.ts` (8 tests, pre-existing, retargeted mocking
> to match the raw-`axios.post` architecture). Backend re-run was not
> performed for this finding — it doesn't consume `shared/api/*` (only
> `shared/validation/*` and `shared/copy/server`, confirmed by grep), so
> the standing rebuild+retest rule doesn't apply here; `npm run build` was
> still run in `shared/` as routine hygiene.

#### 2.2 Mobile hasn't adopted the existing `shared/api/*` factories
- **Code Section:** `mobile/src/api/chat.ts` (18 lines),
  `mobile/src/api/users.ts` (46 lines) vs. `shared/api/chat.ts`,
  `shared/api/users.ts` (already consumed by `web/src/api/client.ts:114-116`
  via `createChatApi`/`createUsersApi`).
- **Affected Apps:** Mobile only needs to change; web is already correct.
- **Similarity:** Identical endpoint list, identical request/response
  shapes. `shared/api/users.ts` is in fact a strict superset — it already
  has `deleteMyPhoto` where mobile's local copy has `deletePhoto` (same
  endpoint, different method name — a naming drift that's already happened
  once because these are two files instead of one).
- **Business Logic Rationale:** Every new backend endpoint currently has to
  be added to `shared/api/*` (for web) *and* hand-copied into mobile's
  `api/*.ts` (or mobile silently doesn't get it). That's a standing
  maintenance tax with no offsetting benefit.
- **Implementation Notes:** Swap `mobile/src/api/chat.ts` and
  `api/users.ts` for `createChatApi(api)` / `createUsersApi(api)` calls
  against mobile's existing `api` Axios instance. Trivial once 2.1's client
  factory (or even just mobile's current `axios.ts`) is in place.
- **Estimated Impact:** ~64 lines deleted from mobile, zero new shared code
  (it already exists). **Risk: Low.**

> ✅ **DONE** — 2026-08-06
> **What changed:** `mobile/src/api/chat.ts` and `mobile/src/api/users.ts` now
> delegate to `createChatApi`/`createUsersApi` from `shared/api/*` instead of
> hand-rolling their own Axios calls. `chat.ts` shrank from 18 to 6 lines with
> no bridging needed (all four methods matched shared's signatures exactly).
> `users.ts` shrank from 46 to 28 lines; it re-exports shared's methods
> directly and keeps three thin, commented bridge methods
> (`deletePhoto` aliasing shared's `deleteMyPhoto`, `updateMyProfile`, and
> `registerPushToken`) where mobile's local types are looser than shared's.
> No caller files, `shared/` files, or mobile type files were touched.
> **Deviations from the report:** none in substance. The report estimated a
> clean ~64-line deletion; in practice three of the twelve `usersApi` methods
> needed a small local bridge (documented inline) because mobile's
> `Profile.gender` is untyped as the shared `Gender` union and `Platform.OS`
> is wider than `'ios' | 'android'` — this was surfaced and approved before
> implementation, see conversation.
> **Tests:** covered by existing suite only (`APP/tests/mobile/*`) — no new
> tests were required for this finding per the project's tests-first rule,
> which applies only to 2.1, 2.11, 2.6, and 2.10.

#### 2.3 Conversation preview formatter (`buildPreview`)
- **Code Section:** `mobile/src/screens/chat/ChatHistoryScreen.tsx:19-31`
  vs. `web/src/components/ChatMasterDetail.tsx:15-40`.
- **Similarity:** Identical: `PREVIEW_MAX = 38`, identical emoji strings for
  `AUDIO`/`IMAGE`, identical truncation with `…`, identical `'את/ה: '`
  self-sender prefix.
- **Business Logic Rationale:** This is the conversation-list preview text
  users see everywhere — a pure, zero-dependency function of a
  `Conversation` object.
- **Implementation Notes:** No platform branching of any kind. Move as-is
  into `shared/utils/` (e.g. `formatConversationPreview.ts`), taking
  `(conv, selfId)`.
- **Estimated Impact:** ~15 duplicate lines removed. **Risk: Low.**

> ✅ **DONE** — 2026-08-06
> **What changed:** Extracted `buildPreview` into a new
> `shared/utils/formatConversationPreview.ts`, exporting
> `formatConversationPreview(conv, selfId)`. Removed the local
> `PREVIEW_MAX`/`buildPreview` definitions from both
> `mobile/src/screens/chat/ChatHistoryScreen.tsx` and
> `web/src/components/ChatMasterDetail.tsx`, and switched both call sites to
> the shared import. Mobile's now-unused local `Conversation` type import was
> also removed from `ChatHistoryScreen.tsx`; web kept its `Conversation`
> import since it's still used elsewhere in that file.
> **Deviations from the report:** none — mobile's and shared's `Conversation`
> types turned out to be structurally identical, so no bridging/casting was
> needed, unlike 2.2.
> **Tests:** covered by existing suite only — no new tests required for this
> finding per the project's tests-first rule (applies only to 2.1, 2.11, 2.6,
> 2.10).

#### 2.4 Candidate meta-line formatter (`metaLine`)
- **Code Section:** `mobile/src/screens/discover/DiscoverScreen.tsx:21-33`
  vs. `web/src/pages/DiscoverPage.tsx:11-31`.
- **Similarity:** Same age-from-DOB math, same gendered Hebrew word choice
  (`בן`/`בת`/`בן/בת`), same `city` fallback, same empty-state string
  `'חבר/ה חדש/ה'`. Only cosmetic difference is separator spacing
  (`'  ·  '` vs `' · '`) — itself a tiny visual inconsistency worth fixing
  as a side effect of unifying.
- **Business Logic Rationale:** Defines how every candidate card presents
  age/location across both discovery surfaces.
- **Implementation Notes:** Pure function of `Candidate`. Move to
  `shared/utils/`.
- **Estimated Impact:** ~13 duplicate lines removed. **Risk: Low.**

> ✅ **DONE** — 2026-08-06
> **What changed:** Extracted the segment-building logic into a new
> `shared/utils/formatCandidateMeta.ts`, exporting
> `formatCandidateMetaSegments(candidate): string[]` and
> `EMPTY_CANDIDATE_META_LABEL`. Both `mobile/src/screens/discover/
> DiscoverScreen.tsx` and `web/src/pages/DiscoverPage.tsx` keep a thin local
> `metaLine` wrapper that calls the shared function and joins the segments
> with their own unchanged separator (`'  ·  '` on mobile, `' · '` on web —
> per explicit instruction, zero visual change on either platform).
> **Deviations from the report:** the shared function takes a small local
> `CandidateMetaInput` type (just `date_of_birth`/`gender`/`city`) instead of
> the domain `Candidate` type, specifically so neither platform's `Candidate`
> (which differ on `gender`'s type, same as 2.2) needed a cast. The
> age-from-DOB formula stays duplicated inline in this new file for now —
> deliberately left for finding 2.5, which consolidates it project-wide.
> **Tests:** covered by existing suite only — no new tests required for this
> finding per the project's tests-first rule (applies only to 2.1, 2.11, 2.6,
> 2.10).

#### 2.5 Peer-profile domain calculations (`genderLabel`, `calcAge`)
- **Code Section:** `mobile/src/screens/peer/PeerProfileScreen.tsx:22-34`
  vs. `web/src/pages/PeerProfilePage.tsx:11-25`.
- **Similarity:** Verbatim duplicate, including the `d.getFullYear() <=
  1900` guard against a zeroed/garbage date-of-birth from the backend.
- **Business Logic Rationale:** "How do we turn a raw `date_of_birth` /
  `gender` into what a user sees" is a single business rule, currently
  defined twice.
- **Implementation Notes:** `calcAge` here duplicates the same
  365.25-day-year math already used independently in
  `shared/validation/profile.ts`'s `validateDateOfBirth` (`MS_PER_YEAR`) —
  three near-identical age calculations exist across the codebase
  (`shared/validation/profile.ts`, mobile's `PeerProfileScreen.tsx`, web's
  `PeerProfilePage.tsx` and `DiscoverPage.tsx`/`DiscoverScreen.tsx`'s
  `metaLine`). Worth consolidating into one `calcAge(dob)` in
  `shared/utils/` that everything else — including the validator — calls.
  Mobile's extra `formatDob` (DD/MM/YYYY display) has no web equivalent
  (web doesn't show raw DOB) — keep that one platform-specific.
- **Estimated Impact:** ~15 duplicate lines removed directly, plus removes
  a 3-way-duplicated age formula. **Risk: Low.**

> ✅ **DONE** — 2026-08-06
> **What changed:** Extracted `calcAge` into a new `shared/utils/calcAge.ts`
> and `genderLabel` into a new `shared/utils/genderLabel.ts`. Removed the
> local duplicates from `mobile/src/screens/peer/PeerProfileScreen.tsx` and
> `web/src/pages/PeerProfilePage.tsx` (mobile's platform-specific `formatDob`
> stayed, as scoped). Also updated `shared/utils/formatCandidateMeta.ts`
> (finding 2.4) to call the new `calcAge` instead of duplicating the age math
> a third time — a verified behavior-preserving refactor (the old
> `if (candidate.date_of_birth) { ... }` guard is equivalent to `calcAge`'s
> own `if (!dob) return null`).
> **Deviations from the report:** deliberately did **not** touch
> `shared/validation/profile.ts`'s internal age calculation, even though the
> report mentions it as a third occurrence worth consolidating. That
> function's age check is structurally different (no `Math.floor`, a
> different date-validity guard) and lives in `shared/validation/`, which
> your standing rules scope tests-first treatment to only for findings 2.6
> and 2.10 — not 2.5. Left as a known, separate duplicate; flagged for your
> call rather than folded in silently.
> **Tests:** covered by existing suite only — no new tests required for this
> finding per the project's tests-first rule (applies only to 2.1, 2.11, 2.6,
> 2.10).

#### 2.6 Profile-form validation chain
- **Code Section:** `mobile/src/screens/profile/ProfileScreen.tsx:100-121`
  vs. `web/src/pages/ProfilePage.tsx:109-174`.
- **Similarity:** Identical precedence and identical `clientMessage` keys:
  `name_required` → `gender_required` → `date_of_birth_required` →
  `city_required` → `validateDateOfBirth` result mapped through
  `invalid_date`/`age_too_young`/`age_too_old`. This ordering is a real
  product decision (which error shows first) that is currently encoded
  imperatively, twice.
- **Business Logic Rationale:** Both platforms must show the exact same
  first-error-wins behavior for the profile form to feel consistent; today
  that consistency is accidental (kept in sync by hand) rather than
  structural.
- **Implementation Notes:** Extract a single
  `validateProfileForm(data): ValidationError` (returning the same
  `clientMessage` key as today) into `shared/validation/profile.ts`,
  alongside the existing `validateDateOfBirth`. Both screens keep their own
  local `useState` fields and call this one function before submitting —
  no React/framework dependency needed in shared.
- **Estimated Impact:** ~20 duplicate lines removed, and — more importantly
  — removes the risk of the two validation orders silently drifting.
  **Risk: Low.**

> ✅ **DONE** — 2026-08-06
> **What changed:** Added `validateProfileForm(input): ProfileFormError |
> null` and its `ProfileFormError`/`ProfileFormInput` types to
> `shared/validation/profile.ts`. Replaced the 8-branch imperative chain in
> both `mobile/src/screens/profile/ProfileScreen.tsx`'s `validateAndSave`
> and `web/src/pages/ProfilePage.tsx`'s `handleSave` with a single call.
> Ran `npm run build` in `shared/` and re-ran the backend suite afterward
> per the standing rule for `shared/validation/` changes.
> **Tests-first (Rule 1):** wrote 10 pinning tests in
> `APP/tests/shared/validation/profile.test.ts` against a local
> verbatim-copied reference implementation of the then-unmodified chain,
> confirmed 20/20 passing (10 pre-existing + 10 new) against the real,
> unmodified `validateDateOfBirth`, got explicit approval of that passing
> run, then implemented `validateProfileForm` and re-pointed the same
> assertions at it — still 20/20 passing, unchanged expectations.
> **Deviations from the report:** web's `gender` state (`Gender | ''`) lost
> a TypeScript narrowing it previously got for free from the inline
> `if (!gender) return;` check now living inside the shared function —
> fixed with a one-line cast (`gender as Gender`) at the `updateMyProfile`
> call site, with a comment explaining why; this is a compile-time-only
> fix, not a runtime behavior change (`validateProfileForm` still guarantees
> the same non-empty precondition before that line is reached).
> **Tests:** `APP/tests/shared/validation/profile.test.ts` —
> `describe('validateProfileForm', ...)`, 10 tests covering all four
> required-field branches in precedence order plus `invalid_date`/
> `age_too_young`/`age_too_old`/happy-path.

#### 2.7 `GENDER_OPTIONS` / `REGION_OPTIONS` domain constants
- **Code Section:** `mobile/src/screens/profile/ProfileScreen.tsx:25-58`
  vs. `web/src/pages/ProfilePage.tsx:14-28`.
- **Similarity:** Identical value/label pairs, identical Hebrew region
  names (`מחוז הצפון`, `מחוז חיפה`, …), identical order.
- **Business Logic Rationale:** This is literally reference data (which
  genders and regions the product supports), not UI — it belongs next to
  `shared/types/user.ts`'s `Gender` type, not copy-pasted per platform.
- **Implementation Notes:** Move to `shared/` (e.g.
  `shared/types/user.ts` companion or a new `shared/reference/` file) as
  plain `{value, label}[]` arrays. Each platform still renders them with its
  own picker component (`ModalPicker` vs `<select>`) — only the data moves.
- **Estimated Impact:** ~20 duplicate lines removed. Adding a region or
  renaming a gender label becomes a one-file change instead of two.
  **Risk: Low** — pure data, no behavior.

> ✅ **DONE** — 2026-08-06
> **What changed:** Created `shared/reference/genderOptions.ts` and
> `shared/reference/regionOptions.ts`, both exporting `Array<{value, label}>`
> as approved. Removed the local literal arrays from
> `mobile/src/screens/profile/ProfileScreen.tsx` and
> `web/src/pages/ProfilePage.tsx`; both now import the shared constants.
> Mobile's `DAY_OPTIONS`/`MONTH_OPTIONS`/`YEAR_OPTIONS` (mobile-only date
> pickers, out of this finding's scope) were untouched.
> **Deviations from the report:** web's `REGION_OPTIONS` was previously a
> flat `string[]` (since region `label` and `value` are always the same
> string); it now consumes the shared `{value,label}[]` shape, so its
> `<select>` rendering changed from `<option key={r} value={r}>{r}</option>`
> to `<option key={r.value} value={r.value}>{r.label}</option>` — the
> rendered `<option>` markup and values are identical since label===value
> for every region, so this is a zero-visible-change mechanical adaptation,
> not a behavior change. `GENDER_OPTIONS`'s JSX needed no change (already
> `{value,label}` shaped on web).
> **Tests:** covered by existing suite only — no new tests required for this
> finding per the project's tests-first rule (applies only to 2.1, 2.11, 2.6,
> 2.10).

#### 2.8 `MAX_PHOTOS` limit
- **Code Section:** `web/src/pages/AdditionalPhotosPage.tsx:12` (named
  const, `= 4`) vs. `mobile/src/screens/profile/AdditionalPhotosScreen.tsx`
  (raw literal `4` used twice, lines ~54 and ~57).
- **Similarity:** Same business rule, but mobile isn't even using a named
  constant for it — a magic number duplicated *within* mobile as well as
  across platforms.
- **Business Logic Rationale:** "How many extra photos can a profile have"
  is a product limit that should be defined once. Today, changing it means
  finding three literal `4`s across two files and hoping none were missed.
- **Implementation Notes:** Add `MAX_ADDITIONAL_PHOTOS` to `shared/config.ts`
  (which already holds `DEFAULT_API_BASE_URL` as "the one place this kind
  of cross-platform literal lives").
- **Estimated Impact:** Tiny in lines, but this is the textbook
  drift-prone constant the project's own `config.ts` comment warns about.
  **Risk: Low.**

> ✅ **DONE** — 2026-08-06
> **What changed:** Added `MAX_ADDITIONAL_PHOTOS = 4` to `shared/config.ts`.
> `mobile/src/screens/profile/AdditionalPhotosScreen.tsx`'s two bare `4`
> literals and `web/src/pages/AdditionalPhotosPage.tsx`'s local
> `MAX_PHOTOS` constant both now reference the shared value.
> **Deviations from the report:** none.
> **Tests:** covered by existing suite only — no new tests required for this
> finding per the project's tests-first rule (applies only to 2.1, 2.11, 2.6,
> 2.10).

### 🟠 Level 4 — HIGHLY RECOMMENDED

#### 2.9 Login-form submit orchestration
- **Code Section:** `mobile/src/screens/login/LoginScreen.tsx:26-44` vs.
  `web/src/pages/LoginPage.tsx:18-51`.
- **Similarity:** Same validation (`!identifier.trim() || !password` →
  `missing_all_fields`), same try/login/navigate-on-success/catch-network-
  error/finally-clear-loading shape, same `AUTH_FLOW_EVENTS.afterLogin`
  lookup.
- **Business Logic Rationale:** The *sequence* of "validate → call → route
  or show error" is a business flow, not incidental UI code.
- **Implementation Notes:** Harder to fully extract than 2.6 because the
  actual navigation call (`navigation.navigate` vs `navigate(...,
  {replace: true})`) has to stay platform-specific. Realistic scope: pull
  just the pre-flight validation (`!identifier.trim() || !password`) out as
  a one-line shared helper, or accept this one stays mostly duplicated
  orchestration and focus effort on 2.10 instead, which has a longer,
  riskier chain.
- **Estimated Impact:** Small (~6 lines) if only validation is extracted.
  **Risk: Low**, but low reward — flagged mainly for consistency with 2.10.

> ✅ **DONE** — 2026-08-06
> **What changed:** Added `validateLoginForm(identifier, password):
> LoginFormError | null` to `shared/validation/credentials.ts`, alongside
> `validateSignupForm`. Replaced the single pre-flight check in both
> `mobile/src/screens/login/LoginScreen.tsx`'s `handleLogin` and
> `web/src/pages/LoginPage.tsx`'s `handleSubmit` with a call to it. Ran
> `npm run build` in `shared/` and re-ran the backend suite afterward per
> the standing rule for `shared/validation/` changes, even though this
> finding wasn't in the tests-first list.
> **Deviations from the report:** none — scoped exactly as the report
> recommended (pre-flight check only; the rest of each screen's
> orchestration — call `login()`, navigate on success, network-error catch
> — stays duplicated, since the navigation call differs per platform).
> **Tests:** covered by existing suite only — not in the tests-first list
> (applies only to 2.1, 2.11, 2.6, 2.10); backend's 187 tests re-confirmed
> passing after the `shared/validation/` change.

#### 2.10 Signup-form submit orchestration
- **Code Section:** `mobile/src/screens/signup/SignupScreen.tsx:30-60` vs.
  `web/src/pages/SignupPage.tsx:20-63`.
- **Similarity:** Identical 3-step validation precedence
  (`missing_all_fields` → `passwords_dont_match` → `password_too_short`),
  identical `deriveUsername(email.trim())` call, identical
  post-signup-navigate-to-login comment/behavior.
- **Business Logic Rationale:** Same reasoning as 2.9, but the validation
  chain here is longer and more likely to drift (three ordered checks
  instead of one).
- **Implementation Notes:** Extract `validateSignupForm({email, password,
  confirm}): ValidationError` into `shared/validation/credentials.ts`
  alongside `validatePassword`/`validatePasswordsMatch`, returning the same
  `clientMessage` keys already used. Each screen still owns its own
  network-error catch and navigation.
- **Estimated Impact:** ~10 duplicate lines removed directly; removes drift
  risk on a 3-step ordered chain. **Risk: Low.**

> ✅ **DONE** — 2026-08-06
> **What changed:** Added `validateSignupForm(input): SignupFormError |
> null` and its `SignupFormError`/`SignupFormInput` types to
> `shared/validation/credentials.ts`. Replaced the 3-branch imperative chain
> in both `mobile/src/screens/signup/SignupScreen.tsx`'s `handleSignup` and
> `web/src/pages/SignupPage.tsx`'s `handleSubmit` with a single call. Each
> screen kept its own `deriveUsername` call, network-error catch, and
> post-signup navigation, exactly as scoped. Ran `npm run build` in
> `shared/` and re-ran the backend suite afterward per the standing rule for
> `shared/validation/` changes.
> **Tests-first (Rule 1):** wrote 9 pinning tests in
> `APP/tests/shared/validation/credentials.test.ts` against a local
> verbatim-copied reference implementation of the then-unmodified chain,
> confirmed 30/30 passing (21 pre-existing + 9 new) against the real,
> unmodified `validatePasswordsMatch`/`validatePassword`, got explicit
> approval of that passing run, then implemented `validateSignupForm` and
> re-pointed the same assertions at it — still 30/30 passing, unchanged
> expectations.
> **Deviations from the report:** none. Confirmed and preserved as a pinned
> test case that the chain never validates email *format* — only presence
> — matching both screens' actual current behavior (`validateEmail` is
> never called here on either platform).
> **Tests:** `APP/tests/shared/validation/credentials.test.ts` —
> `describe('validateSignupForm', ...)`, 9 tests covering all three
> required-field branches, the mismatch/length precedence, and the
> happy path.

#### 2.11 Chat message list controller (load / paginate / send / websocket)
- **Code Section:** `mobile/src/hooks/useConversations.ts` +
  `hooks/useMessages.ts` (~180 lines combined) vs.
  `web/src/components/ChatMasterDetail.tsx:76-343` (~270 lines, because it
  also merges what mobile splits across two screens).
- **Similarity:** Same `PAGE_SIZE = 20`, same reverse-then-prepend
  pagination math, same optimistic-message construction
  (`tmp-${Date.now()}` id, immediate insert, replace-on-confirm,
  remove-on-failure), same three Hebrew error strings
  (`'טעינת השיחות נכשלה...'`, `'טעינת השיחה נכשלה...'`,
  `'שליחת ההודעה נכשלה...'`), same `markRead` fire-and-forget-with-`.catch`
  pattern, same reliance on `shared/utils/reconnectingSocket.ts` (already
  shared) for the actual socket.
- **Affected Apps:** Mobile's `ChatHistoryScreen` + `ChatScreen`; web's
  single master-detail view (a deliberate, documented UX difference — see
  the comment at `ChatMasterDetail.tsx:42-48` — not a bug).
- **Business Logic Rationale:** This is the app's core real-time feature.
  The optimistic-send/reconcile-on-ack state machine and pagination
  bookkeeping is genuinely complex and currently has two independent
  implementations that could silently diverge (e.g. one gets a pagination
  off-by-one fix the other doesn't).
- **Implementation Notes:** Full extraction is **not** trivial — `useState`
  is technically identical between React DOM and React Native (same
  `react` package), so a shared hook is *technically* possible, but
  `shared/`'s Convention 2 ("no React imports") is a deliberate boundary
  the team chose, and web's version also owns extra concerns mobile's
  hooks don't (ack-frame reconciliation via `pendingSendIdsRef`, scroll-
  anchoring). Two realistic paths: **(a)** extract only the pure,
  React-free pieces — pagination math, optimistic-message-object
  construction, the Hebrew error-string constants — into
  `shared/utils/`, leaving the `useState`/`useEffect` wiring duplicated per
  platform (safe, incremental, matches existing conventions); or **(b)**
  make a deliberate architecture call to allow a `react`-dependent shared
  hook for exactly this one stateful controller, given how much duplicated
  complexity it represents. **(a) is the pragmatic default**; **(b)** is a
  bigger call worth a short team discussion, not something to decide
  silently during a refactor.
- **Estimated Impact:** Path (a): ~40–50 lines of pure logic + string
  constants consolidated, moderate maintenance reduction. Path (b): the
  full ~180 vs ~270 lines could shrink toward one ~200-line shared
  controller — high maintenance reduction, but touches the app's riskiest
  real-time code path. **Risk: Medium** (real-time/websocket state is easy
  to subtly break; needs solid test coverage before touching either way).

> ✅ **DONE** — 2026-08-06 (Path (a), per explicit ruling: "no" to a
> `react`-dependent shared hook)
> **What changed:** Three new shared exports: `shared/utils/
> chatPagination.ts` (`CHAT_PAGE_SIZE`, `hasMorePages`),
> `shared/utils/createOptimisticMessage.ts`, and four new `clientMessage`
> keys (`load_conversations_failed`, `load_messages_failed`,
> `load_older_messages_failed`, `send_message_failed`) in
> `shared/copy/client/locales/he.ts`. Updated `mobile/src/hooks/
> useConversations.ts`, `hooks/useMessages.ts`, and
> `web/src/components/ChatMasterDetail.tsx` to use all three. The
> `useState`/`useEffect` wiring, websocket handling, and — per the finding's
> own scoping — ack reconciliation stayed exactly as-is on both platforms,
> per Path (a).
> **Side observation surfaced during this finding (also see new Section 7
> below):** mobile's socket handler has no ack-reconciliation at all — it
> never updates an optimistically-sent message's temp id once it goes out
> over the socket (only web does, via `pendingSendIdsRef`). This is a
> real, pre-existing platform divergence, not something this finding's
> scope (pure logic only) could extract or fix — flagged, not touched.
> **Design decision (approved):** the four error strings now go through
> `clientMessage()`/`shared/copy/client`, the same system every other
> user-facing error in the app already uses, rather than a standalone
> `utils/` constants file — chosen for consistency with the established
> pattern, per your instruction. This is also what directly motivated the
> new Section 7 below.
> **Tests-first (Rule 1):** wrote 9 pinning tests (4 for `hasMorePages`, 5
> for `createOptimisticMessage`) in `APP/tests/shared/utils/
> chatPagination.test.ts` and `createOptimisticMessage.test.ts` against
> local reference copies of the then-unmodified inline logic, confirmed
> 9/9 passing, got explicit approval, implemented the real exports, and
> re-pointed the same assertions — still 9/9 passing. Ack reconciliation
> was not pinned/tested since Path (a) doesn't touch or extract it — no
> new code there to test.
> **Tests:** the two new files above (9 tests) + the pre-existing
> `describe('resolves every key in the he dictionary...')` test in
> `APP/tests/shared/copy/client.test.ts`, which iterates every `he` key and
> automatically covers the 4 new ones — confirmed passing, no edit needed.
> Backend was not re-run — this finding touches `shared/copy/client` and
> `shared/utils/`, neither of which the backend consumes (only
> `shared/validation/*` and `shared/copy/server`) — but `npm run build` was
> still run in `shared/` as routine hygiene.

### 🟡 Level 3 — RECOMMENDED

#### 2.12 Discover pagination bookkeeping
- **Code Section:** `mobile/src/hooks/useCandidates.ts` vs.
  `web/src/pages/DiscoverPage.tsx:50-91` (`loadPage`/`handleLoadMore`).
- **Similarity:** Same `PAGE_SIZE = 20`, same
  `hasMore = data.candidates.length === PAGE_SIZE` heuristic, same
  loading/loadingMore/error state shape, same catch-string
  `'טעינת האנשים נכשלה...'`.
- **Business Logic Rationale:** Same "paginated list" pattern as chat
  (2.11) and photos (2.13) — the third occurrence of this exact shape in
  the codebase.
- **Implementation Notes:** Same fork as 2.11: extract the pure bits
  (page-size constant, `hasMore` rule, error string) now; consider a
  shared generic pagination controller only if the team decides to take on
  a `react`-in-`shared` dependency for 2.11 too — doing it for just one of
  the three call sites isn't worth the abstraction.
- **Estimated Impact:** ~10–15 lines directly; establishes the pattern for
  the other two. **Risk: Low.**

> ✅ **DONE** — 2026-08-06
> **What changed:** New `shared/utils/discoverPagination.ts`
> (`DISCOVER_PAGE_SIZE`, `hasMoreCandidates`) and a new `clientMessage` key
> `load_candidates_failed` in `shared/copy/client/locales/he.ts`. Updated
> `mobile/src/hooks/useCandidates.ts` and `web/src/pages/DiscoverPage.tsx`
> to use both.
> **Deviations from the report:** none — deliberately kept as its own file
> rather than reusing 2.11's `chatPagination.ts`, per the report's own
> Section 4 warning against a generic cross-domain pagination abstraction
> for just three call sites.
> **Tests:** covered by existing suite only (the pre-existing
> `client.test.ts` dictionary-completeness test auto-covers the new key) —
> no new tests required for this finding per the project's tests-first rule
> (applies only to 2.1, 2.11, 2.6, 2.10).

#### 2.13 Photo CRUD flow (load / upload / delete)
- **Code Section:** `mobile/src/hooks/useMyPhotos.ts` vs.
  `web/src/pages/AdditionalPhotosPage.tsx:24-98`.
- **Similarity:** Same three-call shape (`getMyPhotos` → `uploadPhoto` →
  `deletePhoto`/`deleteMyPhoto`), same optimistic list update on success
  (`setPhotos(prev => [...prev, data])` / `.filter(p => p.photo_id !==
  id)`), same three Hebrew error strings.
- **Business Logic Rationale:** Same reasoning as 2.11/2.12.
- **Implementation Notes:** The *trigger* mechanism is genuinely different
  and shouldn't be unified — mobile uses `Alert.alert` with a
  cancel/destructive action sheet, web uses a `ConfirmBanner` component
  with separate `pendingDeleteId`/confirm state. Share the error-string
  constants and the "what happens after a successful delete" list-update
  logic; leave the confirmation UI alone.
- **Estimated Impact:** ~10 lines directly (error strings), moderate risk
  reduction from not hand-copying the three status messages.
  **Risk: Low.**

> ✅ **DONE** — 2026-08-06
> **What changed:** Three new `clientMessage` keys in
> `shared/copy/client/locales/he.ts`: `load_photos_failed`,
> `upload_photo_failed`, `delete_photo_failed`. Updated
> `mobile/src/hooks/useMyPhotos.ts` and
> `web/src/pages/AdditionalPhotosPage.tsx` to use them. Confirmation UI
> (native `Alert.alert` vs. `ConfirmBanner`) and the post-delete list
> `.filter(...)` left untouched, as scoped.
> **Deviations from the report:** the report also suggested sharing the
> "what happens after a successful delete" list-update logic; left that
> inline — it's a single-line `array.filter(p => p.photo_id !== id)`
> directly tied to the local `setPhotos` call, and extracting a
> one-line predicate into its own function would add indirection without
> reducing real duplication, inconsistent with how similar trivial
> one-liners were treated elsewhere this session. Also noted (not acted
> on): `upload_photo_failed`'s Hebrew string is identical to one already
> used in `useMyProfile.ts`/`ProfilePage.tsx`'s main-photo upload, which is
> out of this finding's scope — a natural candidate for Section 7's
> follow-up sweep.
> **Tests:** covered by existing suite only (dictionary-completeness test
> auto-covers the 3 new keys) — no new tests required for this finding per
> the project's tests-first rule (applies only to 2.1, 2.11, 2.6, 2.10).

#### 2.14 Block-user flow
- **Code Section:** `mobile/src/hooks/usePeerProfile.ts:29-54` vs.
  `web/src/pages/PeerProfilePage.tsx:76-105`.
- **Similarity:** Same `usersApi.blockUser(peer_id)` call, same
  success → navigate-away / failure → surface-message shape, same
  catch-string `'החסימה נכשלה. נסה/י שנית.'`.
- **Business Logic Rationale:** Blocking is a trust & safety action;
  keeping the success/failure handling identical across platforms matters
  more than most flows here.
- **Implementation Notes:** Confirmation UI differs (native `Alert.alert`
  vs. `ConfirmBanner` + local `confirmingBlock` state) and should stay
  platform-specific. The async "call block, then either navigate or set an
  error" body is a good candidate for a small shared helper taking
  `(peerId, {onSuccess, onError})` callbacks — same DI pattern already used
  by `createAuthApi(client)`.
- **Estimated Impact:** ~10 lines. **Risk: Low.**

> ✅ **DONE** — 2026-08-06
> **What changed:** New `shared/utils/blockPeer.ts` exports
> `blockPeer(callBlockUser, peerId, { onSuccess, onError })` — the "call
> block, then proceed or surface an error" orchestration, taking the bound
> API call and platform callbacks (same DI pattern as `createAuthApi`).
> Added `block_user_failed` to `shared/copy/client/locales/he.ts`. Updated
> `mobile/src/hooks/usePeerProfile.ts`'s `handleBlock` and
> `web/src/pages/PeerProfilePage.tsx`'s `confirmBlock` to call it, each
> supplying its own `onSuccess`/`onError` (mobile: `onBlocked` callback +
> `Alert.alert`; web: `navigate` + `setBlockError`). Confirmation UI
> (native `Alert.alert` vs. `ConfirmBanner`) untouched, as scoped.
> **Deviations from the report:** none in shape — implemented exactly the
> `(peerId, {onSuccess, onError})` signature the report suggested. One
> care point: `blockPeer` itself never rejects (all paths route to a
> callback), but each call site kept its original `try { await blockPeer
> (...) } finally { setBlocking(false) }` wrapper rather than dropping it,
> so `setBlocking(false)` still runs even if an `onSuccess`/`onError`
> callback itself were to throw — preserves the original code's resilience
> exactly, not just its happy-path behavior.
> **Tests:** covered by existing suite only (dictionary-completeness test
> auto-covers the new key) — no new tests required for this finding per
> the project's tests-first rule (applies only to 2.1, 2.11, 2.6, 2.10).

### 🟢 Level 2 — OPTIONAL

#### 2.15 Photo resize/compression rule exists only on mobile
- **Code Section:** `mobile/src/utils/resizePhoto.ts` (max 1080px longest
  edge, 0.8 JPEG compression) vs. `web/src/components/PhotoUpload.tsx`
  (no client-side resize at all — raw `File` goes straight to
  `usersApi.uploadPhoto`/`uploadMainPhoto`).
- **Similarity:** Not a duplication — the opposite: a business rule
  ("photos get downsized before upload") that exists on one platform and
  silently doesn't on the other.
- **Business Logic Rationale:** This isn't really a *sharing* opportunity
  since `expo-image-manipulator` has no web equivalent to unify against —
  it's flagged here because it's a **product inconsistency** the audit
  surfaced: web users can currently upload full-resolution originals
  (slower uploads, more storage, more backend-side risk) while mobile users
  cannot. Worth a product decision on whether web should get an
  equivalent client-side resize (e.g. via `<canvas>`), independent of code
  sharing.
- **Implementation Notes:** If web adds resizing, the *policy* (1080px /
  0.8 quality / JPEG) belongs in `shared/config.ts` even though the two
  implementations (`expo-image-manipulator` vs. Canvas API) can't be
  shared — a level-2 case: share the constant, not the code.
- **Estimated Impact:** N/A (product decision, not a refactor).
  **Risk: Low** to document, **Medium** if implemented without backend
  coordination (upload size limits, etc.).

### ⚪ Level 1 — NOT RECOMMENDED

#### 2.16 Menu / dashboard screen
- **Code Section:** `mobile/src/screens/menu/MenuScreen.tsx` vs.
  `web/src/pages/MenuPage.tsx`.
- **Similarity:** Low by design. Mobile's Menu is a 3-button hub (it's the
  only navigation mobile has). Web's Menu is a landing dashboard with
  descriptive cards, because `AppShell`'s sidebar already handles
  navigation on web — see the comment at `MenuPage.tsx:32-34` explicitly
  stating this is intentional.
- **Recommendation:** Do not unify. The `PageId`/`QuickLink.to` values
  already route through the shared `pages/pageIds.ts` registry, which is
  the correct level of sharing for this screen. Trying to share more would
  fight a deliberate, documented UX divergence.

#### 2.17 AuthContext bootstrap/session-restore mechanics
- **Code Section:** `mobile/src/auth/useAutoLogin.ts` (SecureStore + hits
  `/auth/me` on boot) vs. `web/src/auth/AuthContext.tsx:38-66` (reads
  stored refresh token, goes through `performRefresh()`).
- **Similarity:** Conceptually similar goal ("restore a session on app
  start"), but the actual mechanics differ enough — mobile validates via
  `/auth/me` against a token it already trusts from SecureStore; web
  proactively rotates via `/auth/refresh` because `sessionStorage` doesn't
  survive a tab close the way SecureStore survives an app relaunch.
- **Recommendation:** Do not force a shared implementation here. The
  `extractUser()` helper (both files, ~4 lines) is trivial enough to move
  to `shared/types/auth.ts` as a pure function if 2.1's client factory
  lands, but the surrounding bootstrap flow should stay platform-specific —
  unifying it would mean encoding two different storage-lifetime
  assumptions into one abstraction, which is exactly the over-engineering
  risk called out in the constraints.

---

## 3. Shared Modules Proposal

No structural changes to `APP/shared`'s existing layout are needed — every
recommendation above fits an existing folder:

```
APP/shared/
    api/
        client.ts          # NEW — createApiClient(baseURL, tokenStorage, onAuthFailure)
                            #   (2.1); auth.ts/users.ts/chat.ts already exist,
                            #   mobile just needs to start importing them (2.2)
    config.ts               # + MAX_ADDITIONAL_PHOTOS (2.8), + resize policy
                            #   constants if 2.15 is acted on
    utils/
        formatConversationPreview.ts   # NEW (2.3)
        formatCandidateMeta.ts         # NEW (2.4)
        calcAge.ts                     # NEW (2.5) — also used by validation/profile.ts
        genderLabel.ts                 # NEW (2.5)
    validation/
        credentials.ts       # + validateSignupForm (2.10)
        profile.ts            # + validateProfileForm (2.6)
    reference/                # NEW folder — pure domain data, not logic
        genderOptions.ts       # (2.7)
        regionOptions.ts       # (2.7)
```

`reference/` is the one new folder suggested — everything else slots into
what's already there. It's kept separate from `types/` because these are
runtime value arrays (rendered in pickers), not TypeScript types.

The chat/discover/photos pagination-and-CRUD controllers (2.11–2.13) are
deliberately **not** given a shared module in this proposal — see those
entries' Implementation Notes. Committing to a shared React hook layer is an
architecture decision (whether `shared/` may depend on `react`) that this
audit surfaces but doesn't make; it should be a short, explicit team
decision before any of that code moves, not an incidental side effect of
extracting the easy wins first.

---

## 4. Risks & Considerations

- **`shared/`'s "no React" rule is a real constraint, not an oversight.**
  Several of the highest-value remaining duplicates (2.11–2.13) are stateful
  controllers built on `useState`/`useEffect`. React itself behaves
  identically in React DOM and React Native, so a shared hook is technically
  possible — but the team already chose not to do this (Convention 2 in
  `shared/README.md`), likely to keep `shared` navigation- and
  render-framework-free as a hedge against a future third client (the admin
  panel already exists as a precedent for "another consumer with different
  needs"). Don't quietly break that convention while chasing line-count
  reduction; make it a deliberate call.

- **Session/auth code is the highest-blast-radius area to touch.** 2.1 is
  the highest-value item in this report and also the one where a subtle
  bug (e.g. getting the single-flight refresh dedup wrong) would be hardest
  to catch in testing and worst in production (silent logouts, or worse,
  a stale token reused after rotation). Any refactor here should ship
  behind strong test coverage of the concurrent-refresh race specifically,
  not just happy-path login/logout.

- **Real-time chat state (2.11) is the second-highest-risk area.** Optimistic
  sends, ack reconciliation, and pagination-while-scroll-anchoring are easy
  to get subtly wrong in a refactor even when the end behavior looks right
  in manual testing. Treat this as a "write tests first" extraction, not a
  quick win.

- **Backend is a `shared` consumer too — a wider blast radius than it
  looks.** Per `shared/README.md`, the backend imports `shared`'s compiled
  `dist/` output (validation + copy) as a real npm dependency, and needs
  `npm run build` re-run after any source change. Any change to
  `validation/credentials.ts` or `validation/profile.ts` (2.6, 2.10) must
  account for the backend picking up the new/changed function too — these
  aren't purely client-side files.

- **Over-engineering risk is concentrated in the pagination-pattern group
  (2.11–2.13).** All three share a shape, which is tempting to generalize
  into one `createPaginatedListController` abstraction. Resist that unless
  a fourth or fifth occurrence shows up — three call sites with genuinely
  different item types (messages, candidates, photos) and different error-
  recovery needs is exactly the "generalization that may add complexity"
  case the Level 2 rubric describes. Extracting the *constants and pure
  math* per-flow (as scoped above) captures most of the value without that
  risk.

- **The existing color-sync test is a good model to replicate.** Where a
  value can't be truly shared (2.15's resize policy, if implemented; web's
  `index.css` Tailwind theme vs. `shared/theme/colors.ts`), the codebase
  already has a working pattern — a test that parses both sources and
  asserts they match — rather than either duplicating silently or forcing
  an awkward shared abstraction. Prefer that pattern over new abstraction
  layers for anything that resists clean extraction.

---

## 5. Quick Wins vs. Long-Term Refactoring

**Quick wins** (low risk, high ratio of drift-risk-removed to effort —
mechanical extraction, no behavior change):

- 2.2 — mobile adopts existing `shared/api/chat.ts` / `users.ts` (deletes
  code, imports what already exists)
- 2.3, 2.4, 2.5 — pure formatter functions (`buildPreview`, `metaLine`,
  `genderLabel`/`calcAge`)
- 2.7 — `GENDER_OPTIONS`/`REGION_OPTIONS` constants
- 2.8 — `MAX_ADDITIONAL_PHOTOS` constant
- 2.6, 2.10 — validation-chain extraction (`validateProfileForm`,
  `validateSignupForm`)

**Long-term / needs a decision first:**

- 2.1 — shared API-client factory (auth refresh/interceptor) — mechanical
  once written, but warrants a careful test pass given the security surface
- 2.11 — chat controller — requires the team to decide whether `shared`
  may depend on `react` before any extraction shape can be chosen
- 2.12, 2.13 — same decision, lower individual stakes; sequence after 2.11
  so the pattern is proven once, not three times
- 2.15 — web-side photo resize — a product decision, not a refactor,
  though it produces a shared *constant* either way

---

## 6. Next Steps & Recommendations

**Phase 1 — Migration debt + pure extractions (quick wins above).**
No architecture decisions required; every item slots into `shared/`'s
existing structure and conventions unchanged. Estimated effort: small — this
is mostly deleting mobile code in favor of what `shared/api/*` already
provides, plus moving ~6 pure functions and 2 constant arrays.

**Phase 2 — API client factory (2.1) + backend coordination check.**
Slightly larger: write `createApiClient`, migrate both platforms onto it,
and re-run the backend's `shared` build/tests since `validation/` changes
from Phase 1 also land in the backend's dependency. Should ship with
explicit test coverage for the concurrent-refresh race. Estimated effort:
medium.

**Phase 3 — Team decision + chat/discover/photo controllers (2.11–2.13).**
Before writing any code: a short, explicit decision on whether `shared/`
takes on a `react` dependency for stateful controllers, or whether these
three stay as "share the pure parts, duplicate the wiring" per this report's
scoping. Whichever way it goes, do 2.11 (chat) first and alone, prove the
pattern and its test coverage, then decide whether 2.12/2.13 are worth
repeating it for. Estimated effort: medium–large, and the riskiest phase —
budget for real-time-specific test coverage before merging.

**Not phased — ongoing:** 2.15 (web photo resize) is a product conversation
to have whenever it's convenient, independent of the phases above; it
doesn't block or get blocked by any of them.

---

## 7. Side Observation — Broader Client-Message Centralization (flagged 2026-08-06)

Not one of the original 17 findings — surfaced while implementing 2.11 and
raised explicitly for documentation here. The `clientMessage`/
`shared/copy/client` system already exists and is the established pattern
for centralizing user-facing strings (used by validation errors since
launch, and — as of finding 2.11 — chat errors too). But a substantial
amount of *other* client-facing text is still duplicated as raw inline
string literals across mobile and web, entirely outside that system.

Confirmed by grep, not just impression:

- `'משתמש/ת'` (the generic "user" display-name fallback) — **13 occurrences
  across 7 files** on both platforms: `ChatHistoryScreen.tsx`/
  `ChatMasterDetail.tsx`, `DiscoverScreen.tsx`/`DiscoverPage.tsx`,
  `PeerProfileScreen.tsx`/`PeerProfilePage.tsx`, `usePeerProfile.ts`.
- `'שגיאה בהעלאת התמונה'` (photo upload failed) — identical across
  `useMyProfile.ts`, `useMyPhotos.ts` (mobile) and `ProfilePage.tsx`,
  `AdditionalPhotosPage.tsx` (web).
- `'שגיאה במחיקת התמונה'` (photo delete failed) — identical across
  `useMyPhotos.ts` (mobile) and `AdditionalPhotosPage.tsx` (web).
- Empty-state strings — `'עדיין אין שיחות. התחילו שיחה ממסך הגילוי 🙂'` and
  `'עדיין אין פרופילים להצגה. חזרו מאוחר יותר 🙂'` — each duplicated once
  per platform.

This is the same shape as 2.3/2.4/2.5 (pure, zero-platform-dependency
strings, safe to centralize) but at a larger scale than any single finding
above scoped in — likely dozens of call sites once swept exhaustively, not
the handful covered incidentally by 2.11's four new `clientMessage` keys.

**Recommendation:** treat as a follow-up candidate, not retroactively folded
into the 17 findings above. A dedicated pass — grep every raw Hebrew string
literal in `mobile/src` and `web/src`, group by exact-match duplicates
across platforms, move each into `shared/copy/client/locales/he.ts` behind
a new `clientMessage()` key — would apply the exact mechanical pattern
already proven safe in this session's work (2.3–2.8, 2.11). Given the
likely volume, this probably warrants its own small set of findings/phases
rather than a single pass.

> ✅ **DONE** — 2026-08-06 (comprehensive sweep, all categories)
> **What changed:** Extended the existing `clientMessage`/`he.ts` pattern
> with **22 new keys** (plus reuse of the existing `upload_photo_failed`
> from finding 2.13) in `shared/copy/client/locales/he.ts`, covering every
> confirmed exact-match Hebrew string literal duplicated across mobile and
> web that this session's exhaustive grep sweep found — not just the
> handful of error/status messages originally flagged above, but also
> shared field labels (`gender_label`, `age_label`, `location_label`,
> `about_me_label`, `more_details_label`), the profile-incomplete sentence,
> the additional-photos label, and shared button/nav labels
> (`password_min_length_hint`, `signup_submit_label`, `login_label`,
> `signup_entry_label`, `save_changes_label`, `back_label`, `close_label`).
> Wired at every confirmed literal call site across **12 mobile files**
> (`hooks/usePeerProfile.ts`, `usePeerPhotos.ts`, `useMyProfile.ts`,
> `useMyPhotos.ts`; `screens/discover/DiscoverScreen.tsx`,
> `screens/chat/ChatHistoryScreen.tsx`, `screens/peer/PeerProfileScreen.tsx`,
> `screens/peer/PeerPhotosScreen.tsx`, `screens/profile/ProfileScreen.tsx`,
> `screens/profile/AdditionalPhotosScreen.tsx`,
> `screens/signup/SignupScreen.tsx`, `screens/welcome/WelcomeScreen.tsx`)
> and **9 web files** (`pages/DiscoverPage.tsx`, `pages/PeerProfilePage.tsx`,
> `pages/PeerPhotosPage.tsx`, `pages/AdditionalPhotosPage.tsx`,
> `pages/ProfilePage.tsx`, `pages/SignupPage.tsx`, `pages/LoginPage.tsx`,
> `pages/WelcomePage.tsx`, `components/ChatMasterDetail.tsx`). Scope was
> explicitly widened from this section's original Category-1-only
> recommendation to all three categories (error messages, field labels,
> button/nav labels) per an explicit approval exchange in the session
> transcript; raw unquoted JSX text content stayed out of scope throughout,
> per the same exchange.
> **Deviations found and corrected during precise per-file implementation
> (flagging rather than silently reconciling, per standing instruction):**
> 1. **False positive dropped:** `PeerProfileScreen.tsx`'s
>    `"להצגת תמונות נוספות"` and `PeerProfilePage.tsx`'s matching JSX-children
>    text were assumed to match `additional_photos_label` in the original
>    plan — they don't (different, longer string; web's side is JSX
>    children besides). Neither was wired for that key.
> 2. **Legitimate addition:** `ProfileScreen.tsx` (mobile) has its own
>    `"מין"` field label, an exact match for `gender_label` that the
>    original per-file plan omitted for this file. Wired it, reusing the
>    same key already planned for `PeerProfileScreen.tsx` — no new key
>    added. Web's own-profile equivalent is JSX children, so this ended up
>    mobile-only for that one call site, which is still a net reduction in
>    duplication (removes an internal mobile-side repeat).
> 3. **Partial/mobile-only key:** `back_label`'s planned web wiring
>    (`PeerPhotosPage.tsx`) turned out to be JSX children at both real call
>    sites — the one "literal" match my original grep found was inside a
>    code *comment*, not real code. `back_label` was therefore wired on
>    mobile only (3 call sites), with web's matching text left as JSX
>    children, out of scope.
> 4. **Similarly partial:** `close_label` — web `DiscoverPage.tsx` has one
>    genuine literal match (`aria-label="סגירה"`, wired) and one JSX-children
>    match (a visible button's text, left alone).
> 5. **Known gap, not filled:** `'הוסף תמונה'` (add-photo label) is a real
>    exact-match duplicate (`AdditionalPhotosScreen.tsx` / `AdditionalPhotosPage.tsx`)
>    that surfaced in this session's very first scan pass but was dropped
>    before the final approved 22-key table and therefore was **not**
>    wired here, to stay strictly within what was actually approved. Noted
>    here as a one-key follow-up candidate.
> **Tests:** covered by existing suite only — the pre-existing
> `client.test.ts` dictionary-completeness test (iterates every `he` key)
> auto-covers all 22 new keys with no edit needed. Not a tests-first
> finding (Rule 1 scopes that to 2.1/2.11/2.6/2.10 only). No
> `shared/validation/` involvement, so no backend rebuild required;
> `npm run build` run in `shared/` as routine hygiene regardless.
> **Verification:** mobile, web, and shared all typecheck clean; web lint
> clean (one pre-existing, unrelated warning in `AuthContext.tsx`); mobile
> (10 tests), web (8 tests), shared (100 tests) all pass.

> ✅ **ADDENDUM** — 2026-08-06 (follow-up on the two items flagged above)
> **Item 1 — `'הוסף תמונה'` gap filled.** Added `add_photo_label` to
> `shared/copy/client/locales/he.ts`. Wired at both of its confirmed exact
> occurrences (re-verified by a fresh grep before implementing — no other
> sites exist): `mobile/src/screens/profile/AdditionalPhotosScreen.tsx`
> and `web/src/pages/AdditionalPhotosPage.tsx`, both on the same ternary
> line that already used `photo_limit_reached`.
> **Item 2 — `close_label` web JSX-children exception.** By explicit,
> narrow approval (the general "no JSX children" rule from the original
> sweep otherwise stays intact), wired the one remaining visible-text site
> in `web/src/pages/DiscoverPage.tsx` (`>סגירה</button>` →
> `>{clientMessage('close_label')}</button>`), bringing it in line with
> mobile's `DiscoverScreen.tsx`, which was already fully wired since its
> `SecondaryButton`'s `text` prop never renders raw children. No other
> `close_label` call site was touched.
> **Tests:** covered by existing suite only — dictionary-completeness test
> auto-covers `add_photo_label`. No new tests required (not a tests-first
> finding); no `shared/validation/` involvement, so no backend rebuild
> needed — `shared` rebuilt anyway as routine hygiene.
> **Verification:** mobile, web, and shared all typecheck clean; web lint
> clean (same one pre-existing, unrelated warning); mobile (10 tests), web
> (8 tests), shared (100 tests) all pass.
