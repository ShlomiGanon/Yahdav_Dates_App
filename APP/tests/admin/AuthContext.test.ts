vi.mock('../../admin/src/api/axios', () => ({
    performRefresh: vi.fn(),
}));

vi.mock('../../admin/src/api/auth', () => ({
    authApi: { logout: vi.fn() },
}));

import { createElement } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { performRefresh } from '../../admin/src/api/axios';
import { authApi } from '../../admin/src/api/auth';
import { tokenStore } from '../../admin/src/api/tokenStore';
import { AuthProvider, useAuth } from '../../admin/src/auth/AuthContext';

const performRefreshMock = performRefresh as unknown as ReturnType<typeof vi.fn>;
const logoutMock         = authApi.logout as unknown as ReturnType<typeof vi.fn>;

// This Node runtime exposes its own experimental global `localStorage`
// (see the `--localstorage-file` warning at startup), which shadows jsdom's
// and is missing basic methods like `.clear()`/`.removeItem()`. Same
// workaround as tests/admin/client.test.ts — replace the global with a
// minimal, fully-working in-memory Storage so both this test file and
// AuthContext's own bare `localStorage` reference consistently hit the
// same working implementation.
function makeMemoryStorage(): Storage
{
    let store: Record<string, string> = {};
    return {
        getItem: (key: string) => (key in store ? store[key] : null),
        setItem: (key: string, value: string) => { store[key] = String(value); },
        removeItem: (key: string) => { delete store[key]; },
        clear: () => { store = {}; },
        key: (index: number) => Object.keys(store)[index] ?? null,
        get length() { return Object.keys(store).length; },
    } as Storage;
}

const memoryStorage = makeMemoryStorage();
Object.defineProperty(globalThis, 'localStorage', { value: memoryStorage, writable: true, configurable: true });
Object.defineProperty(window, 'localStorage', { value: memoryStorage, writable: true, configurable: true });

const ADMIN_USER   = { user_id: 'u1', email: 'admin@test.com',   username: 'admin',   is_admin: true };
const DEMOTED_USER = { user_id: 'u2', email: 'demoted@test.com', username: 'demoted', is_admin: false };

function wrapper({ children }: { children: ReactNode })
{
    return createElement(AuthProvider, null, children);
}

// Mirrors what the real performRefresh() (admin/src/api/axios.ts) does on a
// successful refresh: it persists the rotated tokens unconditionally,
// before AuthContext ever gets a chance to look at is_admin.
function mockSuccessfulRefresh(user: typeof ADMIN_USER | typeof DEMOTED_USER, rotatedRefreshToken: string)
{
    performRefreshMock.mockImplementation(async () =>
    {
        tokenStore.set('rotated-access-token');
        localStorage.setItem('refresh_token', rotatedRefreshToken);
        return user;
    });
}

beforeEach(() =>
{
    performRefreshMock.mockReset();
    logoutMock.mockReset();
    logoutMock.mockResolvedValue({ success: true, message: 'ok' });
    tokenStore.set(null);
    localStorage.clear();
});

describe('AuthContext — session restore', () =>
{
    it('restores a real admin session normally', async () =>
    {
        localStorage.setItem('refresh_token', 'stale-admin-refresh');
        mockSuccessfulRefresh(ADMIN_USER, 'rotated-admin-refresh');

        const { result } = renderHook(() => useAuth(), { wrapper });

        await waitFor(() => expect(result.current.loading).toBe(false));

        expect(result.current.user).toEqual(ADMIN_USER);
        expect(logoutMock).not.toHaveBeenCalled();
    });

    // Regression test 1: a demoted admin (is_admin: false, but the refresh
    // token itself is still valid) must end up with user === null — not a
    // truthy-but-unauthorized user object. RedirectIfAuthed and RequireAuth
    // both branch on `user?.is_admin`; if user were ever truthy here with
    // is_admin false, RedirectIfAuthed would send them away from
    // /admin/login (user is truthy) while RequireAuth would send them right
    // back (is_admin is false) — an infinite loop. Asserting user is null
    // here is what actually rules that out, structurally.
    it('does not leave a demoted admin authenticated after a session restore', async () =>
    {
        localStorage.setItem('refresh_token', 'stale-demoted-refresh');
        mockSuccessfulRefresh(DEMOTED_USER, 'rotated-demoted-refresh');

        const { result } = renderHook(() => useAuth(), { wrapper });

        await waitFor(() => expect(result.current.loading).toBe(false));

        expect(result.current.user).toBeNull();
    });

    // Regression test 2: performRefresh() already persisted the *rotated*
    // tokens (not the original stale ones) before AuthContext saw is_admin
    // was false. A rejected session must revoke that rotated refresh token
    // server-side and clear it locally — otherwise it's still a live,
    // valid session that would just keep silently rotating forever on
    // every future page load, never actually signed out.
    it('revokes the rotated refresh token server-side and clears all local state for a demoted admin', async () =>
    {
        localStorage.setItem('refresh_token', 'stale-demoted-refresh');
        mockSuccessfulRefresh(DEMOTED_USER, 'rotated-demoted-refresh');

        const { result } = renderHook(() => useAuth(), { wrapper });

        await waitFor(() => expect(result.current.loading).toBe(false));

        // The *rotated* token, not the original stale one — proves this
        // reads the post-refresh state back out rather than revoking a
        // token that's already been superseded.
        expect(logoutMock).toHaveBeenCalledWith('rotated-demoted-refresh');
        expect(logoutMock).toHaveBeenCalledTimes(1);
        expect(tokenStore.get()).toBeNull();
        expect(localStorage.getItem('refresh_token')).toBeNull();
    });

    it('clears state without calling logout when performRefresh itself fails', async () =>
    {
        localStorage.setItem('refresh_token', 'stale-refresh');
        performRefreshMock.mockResolvedValue(null);

        const { result } = renderHook(() => useAuth(), { wrapper });

        await waitFor(() => expect(result.current.loading).toBe(false));

        expect(result.current.user).toBeNull();
        expect(logoutMock).not.toHaveBeenCalled();
        expect(localStorage.getItem('refresh_token')).toBeNull();
    });

    it('skips restoring entirely when no refresh token is stored', async () =>
    {
        const { result } = renderHook(() => useAuth(), { wrapper });

        await waitFor(() => expect(result.current.loading).toBe(false));

        expect(performRefreshMock).not.toHaveBeenCalled();
        expect(result.current.user).toBeNull();
    });
});

describe('AuthContext — logout()', () =>
{
    it('logout() revokes the current refresh token and clears state, same as a rejected restore', async () =>
    {
        localStorage.setItem('refresh_token', 'stale-refresh');
        mockSuccessfulRefresh(ADMIN_USER, 'active-refresh');

        const { result } = renderHook(() => useAuth(), { wrapper });
        await waitFor(() => expect(result.current.user).toEqual(ADMIN_USER));

        await result.current.logout();

        expect(logoutMock).toHaveBeenCalledWith('active-refresh');
        expect(tokenStore.get()).toBeNull();
        expect(localStorage.getItem('refresh_token')).toBeNull();
        await waitFor(() => expect(result.current.user).toBeNull());
    });
});
