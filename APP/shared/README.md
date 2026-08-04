# @yahdav/shared

The centralized logic core consumed by web, mobile, and (for validation and
copy) the backend. Nothing here duplicates business logic across platforms —
if a rule, message, or decision needs to exist in more than one place, it
belongs here instead.

## Current structure

```
APP/shared/
    api/            axios client factories — auth.ts, users.ts, chat.ts
    types/          TS types — auth.ts, user.ts, api.ts, chat.ts
    utils/          pure utilities — formatDate.ts
    flow/           session/routing flow rules — authFlow.ts (event +
                    guard rules mapping to a logical AuthDestination,
                    never a concrete route/screen)
    validation/     signup/profile validation rules — credentials.ts,
                    profile.ts
    copy/           i18n message dictionaries — client/ and server/, kept
                    fully separate, each with its own locales/he.ts and
                    resolver (clientMessage / serverMessage)
    theme/          design tokens — colors.ts (color palette; consumed
                    directly by mobile, and by web indirectly — see the
                    CSS caveat below)
    tsconfig.json   standalone TS config, for typechecking this package
                    in isolation (`npx tsc --noEmit`)
    jest.config.js  test runner config — test files live in
                    ../tests/shared, not colocated here
    package.json    also declares subpath `exports` (see note below) and
                    a `build` script — the backend consumes this package
                    as a real npm dependency (via workspaces), not as raw
                    source like web/mobile's bundlers do, so it needs a
                    real compiled `dist/` output. Run `npm run build`
                    here after changing any source file, before the
                    backend can pick up the change.
```

**Consumers:** web and mobile import this package's `.ts` source directly
— their bundlers (Vite, Metro) transpile it themselves, so this package's
own `tsconfig.json`/`module` settings don't affect them. The backend is
different: it's a `tsc`-compiled Node service, so it consumes the real
compiled `dist/` output via an npm workspace dependency
(`APP/package.json` declares `backend` + `shared` as workspace members).
If you add a new subpath here that isn't a flat file directly under one of
these folders (i.e. a `something/index.ts` rather than `something.ts`),
add an explicit entry to `package.json`'s `exports` map for it — the
wildcard fallback (`"./*": "./dist/*.js"`) does a literal string
substitution with no automatic directory-index fallback, so it silently
breaks for directory-shaped modules (`copy/client` and `copy/server`
needed this fix; caught by a real `require()` at test-run time, not by
`tsc`).

**One exception to "consumers import this package's source directly":**
web's colors don't live in a `.ts` file at all — they're Tailwind `@theme`
CSS custom properties in `APP/web/src/index.css`, and CSS can't `import` a
TypeScript module. `theme/colors.ts` is still the source of truth (mobile
imports it directly; web's `index.css` values are hand-kept in sync), but
that sync is enforced by a test
(`APP/tests/shared/theme/colors.test.ts`) that parses `index.css` and
asserts every value matches — not by the compiler. If you change a color,
update both files; the test suite will catch it if you forget one.

## Standing conventions

1. **Deep imports only, no barrel file.** Import as `@shared/api/auth`,
   `@shared/flow/authFlow`, etc. — never add a `@shared/index.ts` that
   re-exports everything. Avoids circular-import risk and keeps
   tree-shaking clean as this package grows.

2. **Framework purity.** Nothing in this package may import React, React
   Native, `react-router`, `@react-navigation`, or reach for
   `window`/`localStorage`/`SecureStore` directly. If logic needs platform
   state, it's passed in by the caller — see `createAuthApi(client)` in
   `api/auth.ts` for the pattern to follow.

3. **Never detect platform or device capability.** No `Platform.OS`, no
   `expo-*` imports (push notifications, etc.) — ever. A capability like
   push exists on mobile and not web; the *platform* decides whether to
   call something, this package never branches on which platform it's
   running under. Same dependency-injection pattern as convention 2: if
   shared logic ever needs to know a capability is available, that gets
   passed in as a parameter by the caller, not detected internally.
   Checked as of Phases 1–3 landing: still zero `Platform.OS`/
   `expo-notifications` references anywhere in this package or in
   `APP/web/src`.

4. **One concept per file, named after its main export.** E.g.
   `formatDate.ts` exports `formatDate`, `flow/authFlow.ts` exports
   `AUTH_FLOW_EVENTS`/`AUTH_FLOW_GUARDS`. Keeps files small and the import
   path self-documenting.

5. **Allman brace style.** `{` always starts a new line, aligned with the
   statement that opens it.

## Testing

Test files live in `APP/tests/shared`, not colocated with source — this
matches the existing pattern in `APP/tests/backend`, `APP/tests/web`, and
`APP/tests/mobile`. Run with `npm test` from this directory (Jest,
`ts-jest`, config in `jest.config.js`).
