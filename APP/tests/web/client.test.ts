import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';

vi.mock('../../web/src/auth/storage', () =>
{
    const state: Record<string, string | null> =
    {
        access_token: null,
        refresh_token: null,
    };

    return {
        webTokenStorage:
        {
            getAccessToken: vi.fn(() => state.access_token),
            setAccessToken: vi.fn((t: string | null) => { state.access_token = t; }),
            getRefreshToken: vi.fn(() => state.refresh_token),
            setRefreshToken: vi.fn((t: string | null) => { state.refresh_token = t; }),
            clear: vi.fn(() =>
            {
                state.access_token = null;
                state.refresh_token = null;
            }),
        },
    };
});

const { axiosClient } = await import('../../web/src/api/client');
const { webTokenStorage } = await import('../../web/src/auth/storage');

const mock = new MockAdapter(axiosClient);

// jsdom doesn't implement real navigation — assigning window.location.href
// (as the interceptor does on an unrecoverable refresh failure) otherwise
// hangs the test. Stub it with a plain writable object for this file only.
const originalLocation = window.location;

beforeEach(() =>
{
    mock.reset();
    webTokenStorage.clear();
    vi.mocked(webTokenStorage.getAccessToken).mockClear();
    vi.mocked(webTokenStorage.setAccessToken).mockClear();
    vi.mocked(webTokenStorage.getRefreshToken).mockClear();
    vi.mocked(webTokenStorage.setRefreshToken).mockClear();
    vi.mocked(webTokenStorage.clear).mockClear();

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
    it('attaches a Bearer header when an access token is stored', async () =>
    {
        webTokenStorage.setAccessToken('token-123');
        mock.onGet('/whoami').reply((config) =>
        {
            expect(config.headers?.Authorization).toBe('Bearer token-123');
            return [200, { ok: true }];
        });

        const res = await axiosClient.get('/whoami');
        expect(res.status).toBe(200);
    });

    it('omits the Authorization header when no token is stored', async () =>
    {
        mock.onGet('/whoami').reply((config) =>
        {
            expect(config.headers?.Authorization).toBeUndefined();
            return [200, { ok: true }];
        });

        await axiosClient.get('/whoami');
    });
});

describe('response interceptor — 401 auto-refresh', () =>
{
    it('refreshes once, then retries the original request with the new token', async () =>
    {
        webTokenStorage.setAccessToken('expired-token');
        webTokenStorage.setRefreshToken('valid-refresh');

        let refreshCalls = 0;
        mock.onPost('/auth/refresh').reply(() =>
        {
            refreshCalls += 1;
            return [200, { access_token: 'fresh-token', refresh_token: 'new-refresh' }];
        });

        let sawFreshToken = false;
        mock.onGet('/protected').reply((config) =>
        {
            if (config.headers?.Authorization === 'Bearer expired-token')
            {
                return [401, { error: 'expired' }];
            }
            sawFreshToken = config.headers?.Authorization === 'Bearer fresh-token';
            return [200, { ok: true }];
        });

        const res = await axiosClient.get('/protected');

        expect(res.status).toBe(200);
        expect(refreshCalls).toBe(1);
        expect(sawFreshToken).toBe(true);
        expect(webTokenStorage.setAccessToken).toHaveBeenCalledWith('fresh-token');
    });

    it('queues concurrent 401s behind a single refresh call', async () =>
    {
        webTokenStorage.setAccessToken('expired-token');
        webTokenStorage.setRefreshToken('valid-refresh');

        let refreshCalls = 0;
        mock.onPost('/auth/refresh').reply(async () =>
        {
            refreshCalls += 1;
            await new Promise((resolve) => setTimeout(resolve, 20));
            return [200, { access_token: 'fresh-token', refresh_token: 'new-refresh' }];
        });

        mock.onGet('/protected').reply((config) =>
        {
            if (config.headers?.Authorization === 'Bearer expired-token')
            {
                return [401, { error: 'expired' }];
            }
            return [200, { ok: true }];
        });

        const [a, b, c] = await Promise.all([
            axiosClient.get('/protected'),
            axiosClient.get('/protected'),
            axiosClient.get('/protected'),
        ]);

        expect(a.status).toBe(200);
        expect(b.status).toBe(200);
        expect(c.status).toBe(200);
        expect(refreshCalls).toBe(1);
    });

    it('clears stored tokens when the refresh call fails at the network level', async () =>
    {
        webTokenStorage.setAccessToken('expired-token');
        webTokenStorage.setRefreshToken('also-invalid');

        // A network-level failure (no response at all) rather than a 401 —
        // see the note below on why a 401 from /auth/refresh itself isn't
        // used here.
        mock.onPost('/auth/refresh').networkError();
        mock.onGet('/protected').reply(401, { error: 'expired' });

        await expect(axiosClient.get('/protected')).rejects.toBeTruthy();

        expect(webTokenStorage.clear).toHaveBeenCalledTimes(1);
    });

    // NOTE — investigated but deliberately not asserted here: making
    // /auth/refresh itself respond 401 (instead of a network error) sends
    // that response back through this same interceptor recursively. Because
    // the interceptor doesn't special-case "this request IS the refresh
    // call," and `_isRefreshing` is already true at that point, the inner
    // 401 gets queued behind the very refresh attempt it's nested inside —
    // a deadlock that hung this suite for 5s+ per run when written as a
    // test. That hang is itself evidence of a real gap (the interceptor has
    // no guard against /auth/refresh responding 401), worth a look — but
    // encoding a test that hangs the suite isn't a reasonable way to track
    // it, so it's flagged here in prose instead.
});
