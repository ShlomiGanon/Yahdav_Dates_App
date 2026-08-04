# WEB_SUPPORT.MD — Web Version Architecture & Implementation Guide

---

## Overview

This document is the single source of truth for building a web version of the Yahdav dating
application. The web app is an **independent React application** (Vite + React 18 + TypeScript +
Tailwind CSS) that lives alongside the mobile app in the repository. The two apps share
**only pure TypeScript** — type definitions, API endpoint factories, and utility functions —
through a common `APP/shared/` folder. They never share a build pipeline, a dependency tree,
or a runtime context.

The mobile app at `APP/mobile/` is treated as **read-only after Phase 0** and is not modified
at any later phase.

---

## Core Principles

1. **Zero Mobile Regression** — Nothing inside `APP/mobile/src/` is touched after the cleanup
   phase. Every screen, every hook, every component, and every native behavior remains exactly
   as it was.

2. **No React Native Web** — The web app is plain React running in a browser, not React Native
   rendered to a DOM. This eliminates version conflicts (`react-native-web` targets React 18;
   mobile runs React 19), avoids native-library translation issues with `@gorhom/bottom-sheet`,
   `react-native-reanimated`, and `react-native-gesture-handler`, and keeps each project's
   dependency tree small and predictable.

3. **Shared Business Logic via `APP/shared/`** — Types, API endpoint factories, and date
   utilities are written once and imported by both projects through a TypeScript path alias.
   Platform-specific concerns (storage, notifications, image picking) are handled separately in
   each project.

4. **Allman Code Style** — Every function body, class body, conditional block, and loop in all
   code examples, templates, and generated files places the opening brace `{` on a new line.
   No exceptions.

---

## Final Target Folder Structure

```
APP/
├── backend/              (unchanged — Express API server)
├── admin/                (unchanged — React admin dashboard)
│
├── mobile/               (React Native / Expo — mobile only, strictly frozen)
│   └── src/
│
├── web/                  (NEW — Vite + React 18 + TypeScript + Tailwind CSS)
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts          axios instance + interceptors + API objects
│   │   ├── auth/
│   │   │   ├── AuthContext.tsx
│   │   │   ├── storage.ts         localStorage / sessionStorage wrappers
│   │   │   └── RequireAuth.tsx
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── DiscoverPage.tsx
│   │   │   ├── ProfilePage.tsx
│   │   │   ├── PeerProfilePage.tsx
│   │   │   ├── ChatHistoryPage.tsx
│   │   │   └── ChatPage.tsx
│   │   ├── components/            reusable UI (Button, Avatar, ChatBubble …)
│   │   ├── hooks/                 data hooks wrapping shared API factories
│   │   ├── App.tsx
│   │   └── main.tsx               entry point — BrowserRouter, AuthProvider
│   ├── index.html                 lang="he" dir="rtl"
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── .env.local                 VITE_API_BASE_URL=http://localhost:3000
│   └── package.json
│
└── shared/               (NEW — platform-agnostic code, imported by both apps)
    ├── types/
    │   ├── auth.ts
    │   ├── user.ts
    │   └── chat.ts
    ├── api/
    │   ├── auth.ts        factory: createAuthApi(axiosInstance)
    │   ├── users.ts       factory: createUsersApi(axiosInstance)
    │   └── chat.ts        factory: createChatApi(axiosInstance)
    └── utils/
        └── formatDate.ts  date-fns, no platform dependencies
```

---

## Phase 0 — Mobile Cleanup ✅ Done

Remove `react-dom` and `react-native-web` from the mobile project and restore it to a
strictly native-only state.

### Step 1 — Uninstall the web packages

```bash
cd APP/mobile
npm uninstall react-dom react-native-web
```

### Step 2 — Remove the `web` script from `package.json`

Open `APP/mobile/package.json` and edit the `scripts` section to remove the `"web"` entry:

```json
"scripts":
{
    "start":   "expo start",
    "android": "expo start --android",
    "ios":     "expo start --ios"
}
```

### Step 3 — Clear Expo and Metro caches

```bash
npx expo start --clear
```

Press `Ctrl+C` once the bundler finishes initialising. The `--clear` flag wipes the Metro
transform cache so no stale web-platform artefacts remain.

### Step 4 — Verify the packages are gone

```bash
npm ls react-dom react-native-web
```

Both should print `(empty)`. The mobile app is now a pure native codebase again.

> **Status after Phase 0:** Mobile fully restored. `react-dom` and `react-native-web` are
> removed. The `"web"` npm script is deleted. No further changes will ever be made to
> `APP/mobile/` as part of the web project.

---

## Separation Strategy

### Why a separate web app instead of React Native Web

| Concern | React Native Web approach | This approach |
|---------|--------------------------|---------------|
| React version | RN Web 0.21 requires React 18; mobile uses React 19 — conflict | No conflict; each app pins its own version |
| Native libraries | `@gorhom/bottom-sheet`, `react-native-reanimated`, gesture-handler all need partial web shims | Pure React components, no shims needed |
| Bundle size | Entire RN runtime ships to the browser | Lean Vite bundle, tree-shaken |
| Mobile risk | Any web-targeted change can accidentally affect native output | Zero: codebases are physically separate |

### The shared layer

`APP/shared/` contains code that has **no platform-specific imports** — no `expo-*`, no
`react-native`, no `window`, no `localStorage`. It is pure TypeScript that compiles in any
environment.

Both projects import from `shared/` via a `@shared` TypeScript path alias configured in each
project's `tsconfig.json` and (for the web app) in `vite.config.ts`.

### API factory pattern

The shared API modules use a **factory function** that accepts an `AxiosInstance` parameter.
Each app creates its own axios instance (with its own interceptors, base URL, and token storage
strategy) and passes it to the factory. The returned object exposes the same typed API surface
on both platforms.

```
Mobile:  mobileAxios  → createUsersApi(mobileAxios)  → usersApi
Web:     webAxios     → createUsersApi(webAxios)     → usersApi
```

---

## Phase 1 — Create the Shared Logic Folder ✅ Done

### Step 1 — Create the directory skeleton

```bash
mkdir APP/shared
mkdir APP/shared/types
mkdir APP/shared/api
mkdir APP/shared/utils
```

### Step 2 — `shared/types/auth.ts`

```typescript
export interface AuthTokens
{
    access_token: string;
    refresh_token: string;
}

export interface AuthUser
{
    user_id:  string;
    email:    string;
    username: string;
    is_admin: number;
}
```

### Step 3 — `shared/types/user.ts`

```typescript
export type UserStatus = 'active' | 'suspended' | 'banned';

export interface Profile
{
    user_id:      string;
    name:         string;
    gender:       string;
    date_of_birth: string | null;
    city:         string;
    region:       string;
    bio:          string;
    looking_for:  string;
    status:       UserStatus;
    photo_urls:   string[];
    updated_at:   string;
}

export interface Candidate
{
    user_id:   string;
    name:      string;
    city:      string;
    photo_url: string | null;
    age:       number | null;
}

export interface PeerProfile
{
    user_id:    string;
    name:       string;
    city:       string;
    region:     string;
    bio:        string;
    looking_for: string;
    photo_urls: string[];
}
```

### Step 4 — `shared/types/chat.ts`

```typescript
export interface Message
{
    message_id: string;
    sender_id:  string;
    content:    string;
    msg_type:   'TEXT' | 'IMAGE';
    created_at: string;
    is_read:    number;
}

export interface Conversation
{
    peer_id:         string;
    peer_name:       string;
    peer_photo:      string | null;
    last_content:    string | null;
    last_message_at: string | null;
    unread_count:    number;
}
```

### Step 5 — `shared/utils/formatDate.ts`

```typescript
import { formatDistanceToNow, isToday, isYesterday, format } from 'date-fns';
import { he } from 'date-fns/locale';

export function formatMessageTime(iso: string): string
{
    return format(new Date(iso), 'HH:mm');
}

export function formatConversationTime(iso: string | null): string
{
    if (!iso)
    {
        return '';
    }

    const date = new Date(iso);

    if (isToday(date))
    {
        const diffMs = Date.now() - date.getTime();

        if (diffMs < 60_000)
        {
            return 'עכשיו';
        }

        return formatDistanceToNow(date, { locale: he, addSuffix: true });
    }

    if (isYesterday(date))
    {
        return 'אתמול';
    }

    return format(date, 'dd/MM', { locale: he });
}
```

### Step 6 — `shared/api/auth.ts`

```typescript
import type { AxiosInstance } from 'axios';
import type { AuthTokens, AuthUser } from '../types/auth';

export function createAuthApi(client: AxiosInstance)
{
    return {
        signup(
            email:    string,
            username: string,
            password: string,
        ): Promise<AuthTokens & { user_id: string }>
        {
            return client
                .post('/auth/signup', { email, username, password })
                .then((r) => r.data);
        },

        login(identifier: string, password: string): Promise<AuthTokens>
        {
            return client
                .post('/auth/login', { identifier, password })
                .then((r) => r.data);
        },

        refresh(refresh_token: string): Promise<AuthTokens>
        {
            return client
                .post('/auth/refresh', { refresh_token })
                .then((r) => r.data);
        },

        logout(refresh_token: string): Promise<void>
        {
            return client
                .post('/auth/logout', { refresh_token })
                .then(() => undefined);
        },

        me(): Promise<AuthUser>
        {
            return client.get('/auth/me').then((r) => r.data);
        },
    };
}
```

### Step 7 — `shared/api/users.ts`

```typescript
import type { AxiosInstance } from 'axios';
import type { Profile, Candidate, PeerProfile } from '../types/user';

export function createUsersApi(client: AxiosInstance)
{
    return {
        getMyProfile(): Promise<Profile>
        {
            return client.get('/users/me').then((r) => r.data);
        },

        updateMyProfile(data: Partial<Profile>): Promise<Profile>
        {
            return client.put('/users/me', data).then((r) => r.data);
        },

        discoverCandidates(page: number, limit: number): Promise<Candidate[]>
        {
            return client
                .get('/users/discover', { params: { page, limit } })
                .then((r) => r.data);
        },

        getPeerProfile(peer_id: string): Promise<PeerProfile>
        {
            return client.get(`/users/${peer_id}`).then((r) => r.data);
        },

        getPeerPhotos(peer_id: string): Promise<{ name: string; photos: string[] }>
        {
            return client.get(`/users/${peer_id}/photos`).then((r) => r.data);
        },

        blockUser(peer_id: string): Promise<void>
        {
            return client
                .post(`/users/${peer_id}/block`)
                .then(() => undefined);
        },
    };
}
```

### Step 8 — `shared/api/chat.ts`

```typescript
import type { AxiosInstance } from 'axios';
import type { Message, Conversation } from '../types/chat';

interface GetMessagesParams
{
    limit?:  number;
    before?: string;
}

export function createChatApi(client: AxiosInstance)
{
    return {
        getConversations(): Promise<Conversation[]>
        {
            return client.get('/chat/conversations').then((r) => r.data);
        },

        getMessages(peer_id: string, params?: GetMessagesParams): Promise<Message[]>
        {
            return client
                .get(`/chat/${peer_id}`, { params })
                .then((r) => r.data);
        },

        sendMessage(
            peer_id:  string,
            content:  string,
            msg_type: string = 'TEXT',
        ): Promise<Message>
        {
            return client
                .post(`/chat/${peer_id}`, { content, msg_type })
                .then((r) => r.data);
        },

        markRead(peer_id: string): Promise<void>
        {
            return client
                .put(`/chat/${peer_id}/read`)
                .then(() => undefined);
        },
    };
}
```

---

## Phase 2 — Initialize the Web Client ✅ Done

### Step 1 — Scaffold the Vite project

Run from the `APP/` directory:

```bash
cd APP
npm create vite@latest web -- --template react-ts
cd web
npm install
```

### Step 2 — Install runtime dependencies

```bash
npm install axios react-router-dom date-fns
```

### Step 3 — Install dev / build dependencies

```bash
npm install -D tailwindcss postcss autoprefixer @types/node
npx tailwindcss init -p
```

### Step 4 — `vite.config.ts` — resolve the shared folder

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(
{
    plugins: [react()],
    resolve:
    {
        alias:
        {
            '@':       path.resolve(__dirname, './src'),
            '@shared': path.resolve(__dirname, '../shared'),
        },
    },
    server:
    {
        port: 5174,
    },
});
```

> Port 5174 is chosen so the web app does not collide with the admin dashboard on 5173.

### Step 5 — `tsconfig.json` — TypeScript path aliases

Replace the generated `tsconfig.json` with:

```json
{
    "compilerOptions":
    {
        "target":            "ES2020",
        "useDefineForClassFields": true,
        "lib":               ["ES2020", "DOM", "DOM.Iterable"],
        "module":            "ESNext",
        "moduleResolution":  "bundler",
        "resolveJsonModule": true,
        "jsx":               "react-jsx",
        "strict":            true,
        "noUnusedLocals":    true,
        "noUnusedParameters": true,
        "baseUrl":           ".",
        "paths":
        {
            "@/*":       ["./src/*"],
            "@shared/*": ["../shared/*"]
        }
    },
    "include": ["src"]
}
```

### Step 6 — `tailwind.config.js` — design tokens from mobile theme

```javascript
/** @type {import('tailwindcss').Config} */
module.exports =
{
    content: ['./index.html', './src/**/*.{ts,tsx}'],
    theme:
    {
        extend:
        {
            colors:
            {
                primary:    '#C0392B',
                secondary:  '#2C3E50',
                background: '#1A1A2E',
                surface:    '#FFFFFF',
                danger:     '#E74C3C',
                success:    '#27AE60',
                selfBubble: '#27AE60',
                peerBubble: '#ECF0F1',
            },
            fontFamily:
            {
                he: ['system-ui', 'sans-serif'],
            },
            borderRadius:
            {
                card:   '16px',
                bubble: '18px',
            },
        },
    },
    plugins: [],
};
```

### Step 7 — `index.html` — Hebrew RTL root

```html
<!doctype html>
<html lang="he" dir="rtl">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>יחדב</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

### Step 8 — `.env.local`

```
VITE_API_BASE_URL=http://localhost:3000
```

### Step 9 — `src/index.css` — Tailwind directives

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

---

## Phase 3 — Platform-Safe Wrappers ✅ Done

### 3.1 — Token Storage

The web app uses `sessionStorage` for the short-lived access token (lost on tab close —
intentional security behaviour) and `localStorage` for the 30-day refresh token.

`APP/web/src/auth/storage.ts`:

```typescript
export const webTokenStorage =
{
    getAccessToken(): string | null
    {
        return sessionStorage.getItem('access_token');
    },

    setAccessToken(token: string | null): void
    {
        if (token)
        {
            sessionStorage.setItem('access_token', token);
        }
        else
        {
            sessionStorage.removeItem('access_token');
        }
    },

    getRefreshToken(): string | null
    {
        return localStorage.getItem('refresh_token');
    },

    setRefreshToken(token: string | null): void
    {
        if (token)
        {
            localStorage.setItem('refresh_token', token);
        }
        else
        {
            localStorage.removeItem('refresh_token');
        }
    },

    clear(): void
    {
        sessionStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
    },
};
```

### 3.2 — Axios Instance & JWT Interceptors

`APP/web/src/api/client.ts`:

```typescript
import axios        from 'axios';
import { createAuthApi }  from '@shared/api/auth';
import { createUsersApi } from '@shared/api/users';
import { createChatApi }  from '@shared/api/chat';
import { webTokenStorage } from '../auth/storage';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:3000';

export const axiosClient = axios.create({ baseURL: BASE_URL });

// ── Request interceptor — attach current access token ──────────────────────
axiosClient.interceptors.request.use((config) =>
{
    const token = webTokenStorage.getAccessToken();

    if (token)
    {
        config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
});

// ── Response interceptor — auto-refresh on 401 ─────────────────────────────
let _isRefreshing      = false;
let _pendingQueue: Array<() => void> = [];

axiosClient.interceptors.response.use(
    (response) => response,
    async (error) =>
    {
        const originalRequest = error.config;

        if (error.response?.status !== 401 || originalRequest._retry)
        {
            return Promise.reject(error);
        }

        if (_isRefreshing)
        {
            return new Promise((resolve) =>
            {
                _pendingQueue.push(() => resolve(axiosClient(originalRequest)));
            });
        }

        originalRequest._retry = true;
        _isRefreshing = true;

        try
        {
            const stored = webTokenStorage.getRefreshToken();

            if (!stored)
            {
                throw new Error('no refresh token stored');
            }

            const { data } = await axiosClient.post('/auth/refresh', { refresh_token: stored });

            webTokenStorage.setAccessToken(data.access_token);
            webTokenStorage.setRefreshToken(data.refresh_token);

            axiosClient.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;

            _pendingQueue.forEach((fn) => fn());
            _pendingQueue = [];

            return axiosClient(originalRequest);
        }
        catch (refreshError)
        {
            webTokenStorage.clear();
            window.location.href = '/login';
            return Promise.reject(refreshError);
        }
        finally
        {
            _isRefreshing = false;
        }
    },
);

// ── Typed API singletons — same surface as mobile's api/ modules ────────────
export const authApi  = createAuthApi(axiosClient);
export const usersApi = createUsersApi(axiosClient);
export const chatApi  = createChatApi(axiosClient);
```

### 3.3 — Auth Context

`APP/web/src/auth/AuthContext.tsx`:

```tsx
import React, { createContext, useContext, useEffect, useState } from 'react';
import { authApi, axiosClient }  from '../api/client';
import { webTokenStorage }       from './storage';
import type { AuthUser }         from '@shared/types/auth';

interface AuthState
{
    user:    AuthUser | null;
    loading: boolean;
    login:   (identifier: string, password: string) => Promise<void>;
    logout:  () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode })
{
    const [user,    setUser]    = useState<AuthUser | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() =>
    {
        const stored = webTokenStorage.getRefreshToken();

        if (!stored)
        {
            setLoading(false);
            return;
        }

        authApi
            .refresh(stored)
            .then((tokens) =>
            {
                webTokenStorage.setAccessToken(tokens.access_token);
                webTokenStorage.setRefreshToken(tokens.refresh_token);
                axiosClient.defaults.headers.common.Authorization =
                    `Bearer ${tokens.access_token}`;
                return authApi.me();
            })
            .then((u) => setUser(u))
            .catch(() => webTokenStorage.clear())
            .finally(() => setLoading(false));
    }, []);

    async function login(identifier: string, password: string): Promise<void>
    {
        const tokens = await authApi.login(identifier, password);

        webTokenStorage.setAccessToken(tokens.access_token);
        webTokenStorage.setRefreshToken(tokens.refresh_token);
        axiosClient.defaults.headers.common.Authorization =
            `Bearer ${tokens.access_token}`;

        const u = await authApi.me();
        setUser(u);
    }

    async function logout(): Promise<void>
    {
        const stored = webTokenStorage.getRefreshToken();

        if (stored)
        {
            await authApi.logout(stored).catch(() =>
            {
                // clear locally even if the server call fails
            });
        }

        webTokenStorage.clear();
        delete axiosClient.defaults.headers.common.Authorization;
        setUser(null);
    }

    return (
        <AuthContext.Provider value={{ user, loading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth(): AuthState
{
    const ctx = useContext(AuthContext);

    if (!ctx)
    {
        throw new Error('useAuth must be used inside AuthProvider');
    }

    return ctx;
}
```

### 3.4 — Route Guard

`APP/web/src/auth/RequireAuth.tsx`:

```tsx
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth }  from './AuthContext';

export function RequireAuth({ children }: { children: React.ReactNode })
{
    const { user, loading } = useAuth();

    if (loading)
    {
        return <div className="min-h-screen bg-background" />;
    }

    if (!user)
    {
        return <Navigate to="/login" replace />;
    }

    return <>{children}</>;
}
```

### 3.5 — Push Notifications

The web app does **not** register a push token. No stub or shim is required. The backend
checks for an `expo_push_token` before sending a notification; when none is stored for a
web session it silently skips delivery. No code change is needed anywhere.

### 3.6 — Image Upload

The web app uses a standard HTML file `<input>` and `FormData`. Neither `expo-image-picker`
nor `expo-image-manipulator` is involved.

`APP/web/src/components/PhotoUpload.tsx`:

```tsx
import React, { useRef } from 'react';

interface Props
{
    onFile: (file: File) => void;
    label?: string;
    disabled?: boolean;
}

export function PhotoUpload({ onFile, label = 'העלה תמונה', disabled = false }: Props)
{
    const inputRef = useRef<HTMLInputElement>(null);

    function handleChange(e: React.ChangeEvent<HTMLInputElement>): void
    {
        const file = e.target.files?.[0];

        if (file)
        {
            onFile(file);
            // reset so the same file can be re-picked
            e.target.value = '';
        }
    }

    return (
        <>
            <input
                ref={inputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={handleChange}
            />
            <button
                type="button"
                disabled={disabled}
                className="px-4 py-2 bg-primary text-white rounded-card
                           disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => inputRef.current?.click()}
            >
                {label}
            </button>
        </>
    );
}
```

### 3.7 — RTL Layout

RTL on the web is handled entirely by `dir="rtl"` on `<html>` (already set in `index.html`).
No JavaScript RTL call is needed. Tailwind's logical-property utilities (`ms-*`, `me-*`,
`ps-*`, `pe-*`) respect the document direction automatically. Never use `ml-*`/`mr-*` in
web components — always use `ms-*`/`me-*` so layout mirrors correctly.

---

## Phase 4 — UI Styling Translation ✅ Done

### Design Token Mapping

All web component classes must use the custom Tailwind names defined in Phase 2. Never use
raw hex colour values in JSX class strings.

| Mobile `theme.ts` token | Value | Tailwind class |
|-------------------------|-------|----------------|
| `palette.primary` | `#C0392B` | `bg-primary` / `text-primary` |
| `palette.secondary` | `#2C3E50` | `bg-secondary` / `text-secondary` |
| `palette.background` | `#1A1A2E` | `bg-background` |
| `palette.surface` | `#FFFFFF` | `bg-surface` |
| `palette.danger` | `#E74C3C` | `bg-danger` / `text-danger` |
| `palette.success` | `#27AE60` | `bg-success` / `text-success` |
| `palette.selfBubble` | `#27AE60` | `bg-selfBubble` |
| `palette.peerBubble` | `#ECF0F1` | `bg-peerBubble` |
| `type.heading` 24 px | — | `text-2xl` |
| `type.body` 16 px | — | `text-base` |
| `type.small` 14 px | — | `text-sm` |
| `radius.card` 16 px | — | `rounded-card` |
| `radius.bubble` 18 px | — | `rounded-bubble` |
| `spacing.lg` 24 px | — | `p-6` / `gap-6` |
| `spacing.md` 14 px | — | `p-3.5` / `gap-3.5` |

### Page Shell Template (Allman Style)

Use this as the base wrapper for every page component:

```tsx
import React from 'react';

interface Props
{
    title:    string;
    children: React.ReactNode;
}

export function PageShell({ title, children }: Props)
{
    return (
        <div className="min-h-screen bg-background text-secondary font-he">
            <div className="max-w-2xl mx-auto px-4 py-8">
                <h1 className="text-2xl font-bold mb-6 text-secondary">
                    {title}
                </h1>
                {children}
            </div>
        </div>
    );
}
```

### Button Template (Allman Style)

```tsx
import React from 'react';

interface Props
{
    onPress:   () => void;
    label:     string;
    variant?:  'primary' | 'secondary';
    loading?:  boolean;
    disabled?: boolean;
}

export function Button(
{
    onPress,
    label,
    variant  = 'primary',
    loading  = false,
    disabled = false,
}: Props)
{
    const base = 'w-full py-4 rounded-card text-lg font-semibold transition-opacity';

    const colours = variant === 'primary'
        ? 'bg-primary text-white'
        : 'border border-secondary text-secondary bg-transparent';

    return (
        <button
            type="button"
            disabled={disabled || loading}
            onClick={onPress}
            className={`${base} ${colours} disabled:opacity-50 disabled:cursor-not-allowed`}
        >
            {loading ? '...' : label}
        </button>
    );
}
```

### Chat Bubble Template (Allman Style)

```tsx
import React from 'react';
import { formatMessageTime } from '@shared/utils/formatDate';

interface Props
{
    content:    string;
    created_at: string;
    isSelf:     boolean;
}

export function ChatBubble({ content, created_at, isSelf }: Props)
{
    const alignment = isSelf ? 'items-end' : 'items-start';
    const colour    = isSelf ? 'bg-selfBubble text-white' : 'bg-peerBubble text-secondary';

    return (
        <div className={`flex flex-col ${alignment} mb-2`}>
            <div className={`max-w-xs px-4 py-2 rounded-bubble ${colour}`}>
                <p className="text-base">{content}</p>
            </div>
            <span className="text-xs text-gray-400 mt-1">
                {formatMessageTime(created_at)}
            </span>
        </div>
    );
}
```

### App Entry Point

`APP/web/src/main.tsx`:

```tsx
import React    from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider }  from './auth/AuthContext';
import App               from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <BrowserRouter>
            <AuthProvider>
                <App />
            </AuthProvider>
        </BrowserRouter>
    </React.StrictMode>,
);
```

`APP/web/src/App.tsx`:

```tsx
import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { RequireAuth }      from './auth/RequireAuth';
import { LoginPage }        from './pages/LoginPage';
import { DiscoverPage }     from './pages/DiscoverPage';
import { ProfilePage }      from './pages/ProfilePage';
import { PeerProfilePage }  from './pages/PeerProfilePage';
import { ChatHistoryPage }  from './pages/ChatHistoryPage';
import { ChatPage }         from './pages/ChatPage';

export default function App()
{
    return (
        <Routes>
            <Route path="/login" element={<LoginPage />} />

            <Route
                path="/*"
                element={
                    <RequireAuth>
                        <Routes>
                            <Route path="/discover"            element={<DiscoverPage />} />
                            <Route path="/profile"             element={<ProfilePage />} />
                            <Route path="/peer/:peer_id"       element={<PeerProfilePage />} />
                            <Route path="/chat"                element={<ChatHistoryPage />} />
                            <Route path="/chat/:peer_id"       element={<ChatPage />} />
                            <Route index                       element={<Navigate to="/discover" replace />} />
                        </Routes>
                    </RequireAuth>
                }
            />

            <Route path="*" element={<Navigate to="/discover" replace />} />
        </Routes>
    );
}
```

---

## Development Workflow

### Port Assignments

| Service | Port | Start command |
|---------|------|---------------|
| Backend | 3000 | `npm run dev` in `APP/backend/` |
| Admin   | 5173 | `npm run dev` in `APP/admin/` |
| Web     | 5174 | `npm run dev` in `APP/web/` |
| Mobile  | Expo | `npx expo start` in `APP/mobile/` |

All four services are independent. Start them in separate terminal tabs. Each reads the
backend URL from its own environment variable — no orchestration layer is required.

### Backend CORS

The backend's `ADMIN_CORS_ORIGIN` env variable currently points to the admin dashboard.
Add the web app origin as well in development:

```
ADMIN_CORS_ORIGIN=http://localhost:5173
```

In production the backend should accept both `https://admin.yahdav.app` and
`https://yahdav.app`. Update the CORS configuration in `APP/backend/src/app.ts` to accept
an array of allowed origins when both are deployed.

---

## What Will Never Be Shared

The following files are mobile-native and must stay inside `APP/mobile/src/`:

| Item | Why it stays in mobile |
|------|----------------------|
| `navigation/` | React Navigation is a native package |
| `screens/` | All layout uses RN `View`, `Text`, `Pressable` |
| `components/` | RN primitives — no equivalent in plain React |
| `I18nManager.forceRTL` | RN layout engine API; web uses CSS `dir` |
| `expo-secure-store` | Native keychain; web uses `localStorage` |
| `expo-notifications` | Native push infrastructure; web has none |
| `expo-image-picker` | Native camera / gallery; web uses `<input>` |
| `expo-image-manipulator` | Native image pipeline; web uses Canvas API |
| `@gorhom/bottom-sheet` | Native sheet; web uses a `<dialog>` or modal |
| `react-native-gesture-handler` | Native touch event system |
| `react-native-reanimated` | Native animation engine |

---

## Summary of Phases

| Phase | What it produces | Touches mobile? | Status |
|-------|-----------------|-----------------|--------|
| 0 — Cleanup | Mobile is restored to native-only state | Yes — removal only | ✅ Done |
| 1 — Shared folder | `APP/shared/` with types, API factories, utils | No | ✅ Done |
| 2 — Web init | `APP/web/` scaffold with Vite, Tailwind, alias config | No | ✅ Done |
| 3 — Wrappers | Web auth, storage, axios client, image upload | No | ✅ Done |
| 4 — UI styling | Page shell, button, chat bubble, entry point | No | ✅ Done |
