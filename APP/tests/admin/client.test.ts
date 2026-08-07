import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import { api } from '../../admin/src/api/axios';
import { tokenStore } from '../../admin/src/api/tokenStore';

const mock = new MockAdapter(api);

// jsdom doesn't implement real navigation — assigning window.location.href
// (as the interceptor does on an unrecoverable refresh failure) otherwise
// hangs the test. Stub it with a plain writable object for this file only.
const originalLocation = window.location;

// This Node runtime exposes its own experimental global `localStorage`
// (see the `--localstorage-file` warning at startup), which shadows jsdom's
// and is missing basic methods like `.clear()`/`.removeItem()`. Replace the
// global with a minimal, fully-working in-memory Storage so both this test
// file and axios.ts's own bare `localStorage` reference consistently hit
// the same working implementation.
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

beforeEach(() =>
{
    mock.reset();
    tokenStore.set(null);
    localStorage.clear();

    // @ts-expect-error — intentionally replacing the read-only jsdom Location
    delete window.location;
    // @ts-expect-error — minimal stand-in, only `.href` is ever written to
    window.location = { href: '' };
});

afterEach(() =>
{
    window.location = originalLocation;
});

describe('request interceptor', () =>
{
    it('attaches a Bearer header from tokenStore', async () =>
    {
        tokenStore.set('token-abc');
        mock.onGet('/whoami').reply((config) =>
        {
            expect(config.headers?.Authorization).toBe('Bearer token-abc');
            return [200, { success: true, message: 'ok' }];
        });

        const res = await api.get('/whoami');
        expect(res.status).toBe(200);
    });

    it('omits the Authorization header when no token is set', async () =>
    {
        mock.onGet('/whoami').reply((config) =>
        {
            expect(config.headers?.Authorization).toBeUndefined();
            return [200, { success: true, message: 'ok' }];
        });

        await api.get('/whoami');
    });
});

// The backend always answers HTTP 200; success/failure lives in the body
// (`{success, message, error?}`). Axios never rejects for these — the
// auto-refresh logic lives in the *success* branch of the interceptor,
// keyed off `data.error === 'unauthorized'`.

describe('response interceptor — auto-refresh on {success:false, error:"unauthorized"}', () =>
{
    it('refreshes once via the shared refreshPromise, then retries with the new token', async () =>
    {
        tokenStore.set('expired-token');
        localStorage.setItem('refresh_token', 'valid-refresh');

        let refreshCalls = 0;
        mock.onPost('/api/auth/refresh').reply(() =>
        {
            refreshCalls += 1;
            return [200, { success: true, message: 'ok', access_token: 'fresh-token', refresh_token: 'new-refresh' }];
        });

        mock.onGet('/protected').reply((config) =>
        {
            if (config.headers?.Authorization === 'Bearer expired-token')
            {
                return [200, { success: false, message: 'יש להתחבר מחדש', error: 'unauthorized' }];
            }
            return [200, { success: true, message: 'ok', sawFreshToken: config.headers?.Authorization === 'Bearer fresh-token' }];
        });

        const res = await api.get('/protected');

        expect(res.status).toBe(200);
        expect(res.data.success).toBe(true);
        expect(res.data.sawFreshToken).toBe(true);
        expect(refreshCalls).toBe(1);
        expect(tokenStore.get()).toBe('fresh-token');
        expect(localStorage.getItem('refresh_token')).toBe('new-refresh');
    });

    it('deduplicates concurrent unauthorized responses behind a single shared refreshPromise', async () =>
    {
        tokenStore.set('expired-token');
        localStorage.setItem('refresh_token', 'valid-refresh');

        let refreshCalls = 0;
        mock.onPost('/api/auth/refresh').reply(async () =>
        {
            refreshCalls += 1;
            await new Promise((resolve) => setTimeout(resolve, 20));
            return [200, { success: true, message: 'ok', access_token: 'fresh-token', refresh_token: 'new-refresh' }];
        });

        mock.onGet('/protected').reply((config) =>
        {
            if (config.headers?.Authorization === 'Bearer expired-token')
            {
                return [200, { success: false, message: 'יש להתחבר מחדש', error: 'unauthorized' }];
            }
            return [200, { success: true, message: 'ok' }];
        });

        const [a, b, c] = await Promise.all([
            api.get('/protected'),
            api.get('/protected'),
            api.get('/protected'),
        ]);

        expect(a.data.success).toBe(true);
        expect(b.data.success).toBe(true);
        expect(c.data.success).toBe(true);
        expect(refreshCalls).toBe(1);
    });

    it('clears the token and stored refresh token when there is no refresh token to use', async () =>
    {
        tokenStore.set('expired-token');
        // No refresh_token in localStorage at all.
        mock.onGet('/protected').reply(200, { success: false, message: 'יש להתחבר מחדש', error: 'unauthorized' });

        const res = await api.get('/protected');

        expect(res.data.success).toBe(false);
        expect(tokenStore.get()).toBeNull();
        expect(window.location.href).toBe('/admin/login');
    });

    it('clears tokens when the refresh call fails at the network level', async () =>
    {
        tokenStore.set('expired-token');
        localStorage.setItem('refresh_token', 'also-invalid');

        mock.onPost('/api/auth/refresh').networkError();
        mock.onGet('/protected').reply(200, { success: false, message: 'יש להתחבר מחדש', error: 'unauthorized' });

        const res = await api.get('/protected');

        expect(res.data.success).toBe(false);
        expect(tokenStore.get()).toBeNull();
        expect(localStorage.getItem('refresh_token')).toBeNull();
    });

    // Regression coverage for a real bug found while testing the OLD
    // status-code-based interceptor: making /auth/refresh itself respond
    // with an auth failure recursed back through this same interceptor and
    // deadlocked on the shared `refreshPromise`, since nothing special-cased
    // "this request IS the refresh call." The new error-CODE-based design
    // (`error === 'unauthorized'`) is structurally immune: /auth/refresh's
    // own failure codes (session_not_found, session_expired, invalid_token,
    // ...) are never `unauthorized` — that code only ever comes from the
    // `authenticate` middleware, which /auth/refresh doesn't go through.
    it('does not deadlock when /auth/refresh responds with a non-"unauthorized" failure', async () =>
    {
        tokenStore.set('expired-token');
        localStorage.setItem('refresh_token', 'expired-refresh-too');

        mock.onPost('/api/auth/refresh').reply(200, {
            success: false, message: 'ההתחברות פגה, יש להתחבר מחדש', error: 'session_expired',
        });
        mock.onGet('/protected').reply(200, { success: false, message: 'יש להתחבר מחדש', error: 'unauthorized' });

        const res = await api.get('/protected');

        expect(res.data.success).toBe(false);
        expect(tokenStore.get()).toBeNull();
    });
});
