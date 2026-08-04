# @yahdav/web

React web app for יחדיו's end-users — the browser counterpart to the
mobile app. Hebrew-first, RTL everywhere. For the system-wide picture
(how this fits with backend/admin/mobile/shared), see `../project.md` and
`../architecture.md`.

## Current structure

```
web/
    src/
        pages/          one component per page — the concrete
                        implementation of every PageId declared in
                        @shared/pages/pageIds. Some are fully built
                        (LoginPage, SignupPage, ProfilePage), others are
                        still placeholder stubs — see next_missions.md.
        pages/routes.ts  PAGE_ROUTES — this platform's concrete path for
                        every PageId (`as const satisfies
                        Record<PageId, string>`; won't compile if a page
                        is missing a route)
        auth/           AuthContext, RequireAuth / RedirectIfAuthed route
                        guards, destinations.ts (derives WEB_DESTINATIONS
                        from PAGE_ROUTES), storage.ts (token storage)
        api/client.ts   the axios instance + typed API singletons
                        (authApi/usersApi/chatApi from @shared/api),
                        plus the refresh-on-`unauthorized` interceptor
        components/     PageShell (the only reusable page wrapper) and a
                        handful of small UI primitives
        App.tsx         route registration — every route comes from
                        PAGE_ROUTES, no hardcoded path literals
    next_missions.md    tracked list of stub pages and what each still
                        needs — check this before assuming a page is
                        unfinished by accident vs. by design
    vite.config.ts      dev server fixed to port 5174; @shared alias
                        points at ../shared's raw .ts source
```

**Consumes `@shared` as raw source** — Vite transpiles it directly, no
build step needed on the shared side for web to pick up a change (unlike
the backend, which needs `shared`'s compiled `dist/`).

## Standing conventions

1. **No page calls `axios` directly.** All network calls go through
   `api/client.ts`'s `authApi` / `usersApi` / `chatApi`.

2. **No hardcoded route paths.** Every `<Route path=...>` and every
   redirect target comes from `PAGE_ROUTES` (or `WEB_DESTINATIONS`, which
   itself derives from `PAGE_ROUTES`) — never a bare string literal.

3. **Stub page pattern.** A not-yet-built page is a component wrapped in
   `<PageShell title="...">` with a single placeholder sentence ending in
   "...יוצג/יוצגו כאן" ("...will be shown here"), routed and reachable at
   its real URL, no logic. See any page listed in `next_missions.md`.

4. **Allman brace style.** `{` always starts a new line.

## Testing

Vitest (`npm test`), config in `vitest.config.ts`. Auth/API tests use
`axios-mock-adapter` rather than a real backend.

## Running locally

```
npm install
npm run dev    # http://localhost:5174
```

Requires the backend running on `http://localhost:3000` (the default
`VITE_API_BASE_URL`) — see `../project.md` → Running Locally.
