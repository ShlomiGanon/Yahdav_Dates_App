# Admin Dashboard Plan — React + TypeScript

> **Status:** ✅ Complete
> **Depends on:** `APP/MASTER_PLAN.md`, `APP/backend/BACKEND_PLAN.md`

---

## 1. Overview

Browser-based dashboard for administrators. Consumes `/admin/*` REST endpoints. Phase 1: user management only. Architecture supports adding new sections by dropping files into an established pattern — no restructuring required.

---

## 2. Technology Stack

| Component | Choice |
|-----------|--------|
| Framework | React 18 + TypeScript |
| Build | Vite |
| Routing | React Router v6 |
| HTTP | Axios (JWT interceptor) |
| Styling | Tailwind CSS |
| Forms | React Hook Form + Zod |
| Tables | TanStack Table v8 |
| Dates | `date-fns` (Hebrew locale) |

---

## 3. Folder Structure

```
admin/src/
├── main.tsx                    # React root, Router
├── App.tsx                     # top-level routes
│
├── api/
│   ├── axios.ts                # instance + JWT interceptor
│   ├── auth.ts                 # login, logout, refresh
│   └── users.ts                # admin user CRUD
│
├── auth/
│   ├── AuthContext.tsx         # admin user state + actions
│   ├── LoginPage.tsx           # /login
│   └── RequireAuth.tsx         # route guard
│
├── layout/
│   ├── AppShell.tsx            # sidebar + topbar + <Outlet>
│   ├── Sidebar.tsx             # driven by SECTION_REGISTRY
│   └── Topbar.tsx              # current user + logout
│
├── sections/
│   ├── _registry.ts            # SECTION_REGISTRY array
│   └── users/
│       ├── index.ts            # exports { route, navItem }
│       ├── UserListPage.tsx    # /admin/users
│       ├── UserDetailPage.tsx  # /admin/users/:id
│       └── hooks/
│           ├── useUsers.ts     # list + pagination state
│           └── useUser.ts      # single user + mutations
│
└── components/
    ├── Button.tsx, Badge.tsx, Avatar.tsx
    ├── Table.tsx, Pagination.tsx, SearchInput.tsx
    ├── ConfirmDialog.tsx, StatusSelect.tsx
```

---

## 4. Routing

```
/login             LoginPage (public)
/admin             AppShell (auth-guarded)
  /admin/users     UserListPage
  /admin/users/:id UserDetailPage
```

---

## 5. Extensibility Pattern

`SECTION_REGISTRY` drives both sidebar nav and React Router routes. Adding a new section:
1. Create `sections/<name>/` with `index.ts` exporting `{ route, navItem }`
2. Add one entry to `_registry.ts`
3. Zero changes to layout or routing code

```
// _registry.ts
SECTION_REGISTRY = [
  usersSection,
  // moderationSection  ← uncomment when built
]

// sections/users/index.ts
usersSection = {
  navItem: { label:"משתמשים", icon:UsersIcon, path:"/admin/users" },
  route:   { path:"users", children: [ index→UserListPage, ":id"→UserDetailPage ] }
}
```

---

## 6. User Management

### User List (`/admin/users`)
- Paginated table: avatar · name · username · email · status badge · registered · last login
- Server-side pagination (limit/offset)
- Search by name/email/username — debounced → `GET /admin/users?search=`
- Status filter dropdown: All / Active / Suspended / Pending / Deactivated / Deleted
- Row click → `/admin/users/:id`

### User Detail (`/admin/users/:id`)
- Read-only profile fields + photo thumbnails
- Status dropdown → `PUT /admin/users/:id/status` (optimistic update)
- Delete button → `ConfirmDialog` → `DELETE /admin/users/:id` → redirect to list
- Account info: email · username · registered date · last login · failed login attempts

---

## 7. Authentication Flow

```
Access token:   React state (lost on reload)
Refresh token:  httpOnly cookie (set by backend Set-Cookie)

page reload:
  access_token missing → POST /auth/refresh (cookie auto-sent)
                       → restore access_token silently

on 401:
  interceptor → refresh once → retry → second 401 → force logout
```

Backend enforces `is_admin = 1` on every `/admin/*` request. Frontend hiding is UI-only.

---

## 8. API Layer

```
// api/axios.ts
instance with baseURL = VITE_API_BASE_URL
request interceptor:  attach Bearer <access_token>
response interceptor: on 401 → refresh → retry → logout on second 401

// api/users.ts
getUsers({ limit, offset, search? }) → UserListResponse
getUser(id)                           → UserDetail
updateUserStatus(id, status)          → UserSummary
deleteUser(id)                        → void
```

---

## 9. RTL & Hebrew

- `<html dir="rtl">` in `index.html` — flips Tailwind layout automatically
- Tables: columns read right-to-left
- Pagination: prev/next arrows swap sides
- Dates: `date-fns` with `he` locale (`dd/MM/yyyy`)

---

## 10. Dev Setup

```bash
cd APP/admin
npm create vite@latest . -- --template react-ts
npm install
cp .env.example .env.local   # VITE_API_BASE_URL=http://localhost:3000
npm run dev                   # :5173
```

---

## 11. Future Sections

| Section | Endpoints | Notes |
|---------|-----------|-------|
| Safety Moderation | `PUT /admin/users/:id/safety-flags` | Review reported users |
| Message Review | `GET /admin/conversations/:id/messages` | Moderation audit trail |
| Analytics | New read-only endpoints | Growth charts |
| Push Broadcast | New admin endpoint | Send announcements |

Each = new folder under `sections/` + one line in `_registry.ts`.
