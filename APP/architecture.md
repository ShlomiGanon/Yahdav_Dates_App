# Architecture & Engineering Philosophy — יחדיו (Yahdav)

A high-level map of how this codebase thinks, not what it does. For "what,"
see `project.md`. This document is for a developer or manager who needs to
get oriented fast and start making decisions that fit the grain of the
system, not fight it.

---

## 1. Design Philosophy

**Explicit over implicit.** The system consistently refuses to let meaning
hide in a side channel. The clearest expression of this is the API
contract: every backend response is HTTP 200, and success/failure lives
entirely in the body (`{ success, message, error? }`) — not in the status
code. That was a deliberate, discussed decision, not an oversight: HTTP
status codes conflate transport-level and business-level failure, and this
system wants them kept apart. The same instinct shows up everywhere else —
a machine-readable `error` code and a human-readable `message` are always
two separate fields, never one string doing double duty.

**Single source of truth, enforced by proof, not convention.** Wherever
the same fact could plausibly need to exist twice (a validation rule, a
piece of user-facing copy, a routing decision, a color, a page's own
identity), the system drives it into one place and makes every consumer
read from there. Crucially, "centralized" is never taken on faith — it's
repeatedly caught *not* being true in practice (a mobile screen silently
forking a bug-fixed copy of a "shared" date formatter; a color palette
hand-copied between a CSS file and a TS file; web and mobile once having
their own independently-named idea of what to call the same profile
screen) and each time the fix wasn't just "make it match" but "make it
structurally impossible to drift again" — usually a test, or a compiler
error, that would fire the moment the two copies disagreed, since some of
these boundaries (CSS custom properties, cross-package module resolution)
can't be caught by the type checker at all. The page/screen inventory
itself follows the same discipline: `shared/pages/pageIds.ts` is the one
place a page's identity (`'profile'`, `'discover'`, …) is declared: every
platform's own route table (web's `pages/routes.ts`) or screen-name table
(mobile's `navigation/screenNames.ts`) is a `Record<PageId, ...>` that
TypeScript refuses to compile if it doesn't cover every page shared
declares — adding a page to `shared` without updating both platforms is a
compile error, not a silent gap.

**Verify by running it, not by reading it.** A passing `tsc --noEmit` is
treated as necessary and never sufficient. Every change that crosses a
real execution boundary — a new shared module a bundler has to resolve, a
new package a Node runtime has to `require()`, a new CSS value a browser
has to render — gets proven by actually executing that boundary: a live
bundler request, a real compiled server booted and hit with `curl`, a
browser driven end-to-end. The type checker catches shape; only running
the thing catches whether it actually resolves and behaves.

**Platform-idiomatic, not platform-uniform.** The three client apps don't
share UI, and they're not forced into an artificial common shape. Mobile
screens delegate their data and actions to custom hooks; web pages hold
the same kind of state inline, without a hooks layer; the admin panel is
organized as a registry of self-contained "sections." Each is the natural
idiom for its own framework. What *is* forced to be identical across
platforms is business meaning — the same validation rule, the same
routing decision, the same copy — never markup or component structure.

**Minimalism as a constraint, not an aesthetic.** No ORM (the backend
talks to SQLite through Node's own built-in driver with hand-written
parameterized SQL). No barrel files, anywhere. No abstraction introduced
for a need that doesn't exist yet — a documented convention was chosen
over a speculative pattern more than once specifically because nothing
was actually using it yet. When two things look similar but serve
different purposes (e.g. a generic "fill in all fields" message versus a
field-specific one), they're kept as two things rather than collapsed
into one for the sake of tidiness.

---

## 2. Structure & Flow

The system is five packages around one authority:

- **`backend`** — Node/Express/TypeScript. The single source of truth for
  data and business rules. Nothing else touches the database.
- **`web`**, **`mobile`**, **`admin`** — three independent client
  applications (React/Vite, Expo/React Native, React/Vite respectively).
  None of them talk to each other; all of them talk only to `backend`,
  over HTTP and, for chat, WebSocket.
- **`shared`** — a pure-TypeScript package that sits *beside* all four,
  not beneath any one of them. It owns business logic that would
  otherwise have to exist redundantly in multiple places: validation
  rules, auth/session routing decisions, user-facing copy, typed API
  client factories, and design tokens. It has zero framework
  dependencies — no React, no React Native, no Express — and each
  consumer wires it in using whatever mechanism its own toolchain
  actually needs (a bundler alias for web and mobile; a real installed
  npm workspace dependency with a compiled build step for the
  `tsc`-based backend, since a bundler and a compiler resolve modules
  differently).

**Backend, layered top to bottom:** an HTTP/WS route receives a request →
validation runs (increasingly backed by `shared`'s rules rather than
duplicated locally) → a **Model** executes business logic in plain
functions with no framework awareness of its own → a **Queries** layer
issues hand-written parameterized SQL → a single lazily-created SQLite
connection (WAL mode, foreign keys on). Models return DTOs shaped for the
wire, never raw database rows. Chat's WebSocket path reuses this exact
same Model layer — a message sent over the socket persists through the
identical code a REST call would use, so realtime and REST are two
transports over one business layer, not two divergent implementations. An
in-memory connection registry tracks who's online for direct delivery;
anyone offline gets a push notification instead, using the same
just-persisted message.

**A client request, end to end:** a screen/page collects input → hands it
to a typed API client factory from `shared/api` (constructed once per
platform around that platform's own axios instance and interceptors) →
the backend validates, executes, and always answers 200 → the client
reads `.success`/`.message` directly off the response, no `try/catch`
needed for ordinary business failures, only for genuine network errors.

**Auth is the clearest example of the shared/platform split in practice.**
*Where* a token physically lives is platform-specific by necessity —
`SecureStore` on mobile, a deliberate `sessionStorage`/`localStorage`
split on web — and each platform's storage module owns that. But *what
happens next* — where a successful login sends you, where an expired
session sends you, whether a signup logs you in automatically (it
doesn't, on purpose) — is one small set of event/guard rules in `shared`,
and each platform just translates a logical outcome ("home," "login")
into its own concrete route or screen name. Access tokens are short-lived
JWTs; refresh tokens rotate on every use and are only ever stored
server-side as a hash, never in plaintext.

---

## 3. Leading Principles

A short list of rules this codebase treats as load-bearing, not stylistic:

1. **Every backend response is HTTP 200.** Failure is `success: false` in
   the body, with a machine-readable `error` code and a separate
   human-readable `message`. Nothing downstream branches on status code.
2. **`shared` never imports a framework and never detects a platform.**
   No React/React Native/router imports; no `Platform.OS`, no `expo-*`
   checks. If shared logic needs platform-specific state or capability,
   the caller passes it in — shared code never reaches out for it.
3. **Deep imports only.** Consumers import a specific module
   (`@shared/flow/authFlow`), never a barrel `index.ts`. There isn't one.
4. **One concept, one file, named after its main export.**
5. **Refresh tokens rotate on use and are stored hashed, never in
   plaintext.** A used or expired refresh token is rejected outright, not
   silently accepted.
6. **A passing type check is not proof of a working system.** Anything
   that crosses a real module-resolution or rendering boundary gets
   verified by actually executing it before it's considered done.
7. **Allman brace style** throughout — `{` always opens on its own line.

---

*For what the product does and how to run each app, see `project.md`. For
the shared package's own internal conventions and structure, see
`shared/README.md`.*
