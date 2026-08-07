import { describe, it, expect, vi, beforeEach, afterEach, afterAll } from 'vitest';
import axios from 'axios';
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

// createApiClient's refresh call deliberately uses a raw axios.post rather
// than the interceptor-wired client instance (see shared/api/client.ts —
// APP/review.md finding 2.1), so it needs its own mock adapter mounted on
// the global axios module; axiosClient's adapter can't see it. Matched by
// RegExp since the raw call uses a full absolute URL
// (`${baseURL}/api/auth/refresh`), not the relative path axiosClient's
// baseURL-relative requests use.
const clientMock  = new MockAdapter(axiosClient);
const refreshMock = new MockAdapter(axios);

// jsdom doesn't implement real navigation — assigning window.location.href
// (as the interceptor does on an unrecoverable refresh failure) otherwise
// hangs the test. Stub it with a plain writable object for this file only.
const originalLocation = window.location;

beforeEach(() =>
{
    clientMock.reset();
    refreshMock.reset();
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

afterAll(() =>
{
    // Unmount from the shared global axios module so this file's mocking
    // can't leak into any other test file's use of raw axios.
    refreshMock.restore();
});

describe('request interceptor', () =>
{
    it('attaches a Bearer header when an access token is stored', async () =>
    {
        webTokenStorage.setAccessToken('token-123');
        clientMock.onGet('/whoami').reply((config) =>
        {
            expect(config.headers?.Authorization).toBe('Bearer token-123');
            return [200, { success: true, message: 'ok' }];
        });

        const res = await axiosClient.get('/whoami');
        expect(res.status).toBe(200);
    });

    it('omits the Authorization header when no token is stored', async () =>
    {
        clientMock.onGet('/whoami').reply((config) =>
        {
            expect(config.headers?.Authorization).toBeUndefined();
            return [200, { success: true, message: 'ok' }];
        });

        await axiosClient.get('/whoami');
    });
});

// The backend always answers HTTP 200; success/failure lives in the body
// (`{success, message, error?}`). Axios never rejects for these — the
// auto-refresh logic lives in the *success* branch of the interceptor,
// keyed off `data.error === 'unauthorized'`.

describe('response interceptor — auto-refresh on {success:false, error:"unauthorized"}', () =>
{
    it('refreshes once, then retries the original request with the new token', async () =>
    {
        webTokenStorage.setAccessToken('expired-token');
        webTokenStorage.setRefreshToken('valid-refresh');

        let refreshCalls = 0;
        refreshMock.onPost(/\/api\/auth\/refresh$/).reply(() =>
        {
            refreshCalls += 1;
            return [200, { success: true, message: 'ok', access_token: 'fresh-token', refresh_token: 'new-refresh' }];
        });

        let sawFreshToken = false;
        clientMock.onGet('/protected').reply((config) =>
        {
            if (config.headers?.Authorization === 'Bearer expired-token')
            {
                return [200, { success: false, message: 'יש להתחבר מחדש', error: 'unauthorized' }];
            }
            sawFreshToken = config.headers?.Authorization === 'Bearer fresh-token';
            return [200, { success: true, message: 'ok' }];
        });

        const res = await axiosClient.get('/protected');

        expect(res.status).toBe(200);
        expect(res.data.success).toBe(true);
        expect(refreshCalls).toBe(1);
        expect(sawFreshToken).toBe(true);
        expect(webTokenStorage.setAccessToken).toHaveBeenCalledWith('fresh-token');
    });

    it('shares a single in-flight refresh across concurrent unauthorized responses', async () =>
    {
        webTokenStorage.setAccessToken('expired-token');
        webTokenStorage.setRefreshToken('valid-refresh');

        let refreshCalls = 0;
        refreshMock.onPost(/\/api\/auth\/refresh$/).reply(async () =>
        {
            refreshCalls += 1;
            await new Promise((resolve) => setTimeout(resolve, 20));
            return [200, { success: true, message: 'ok', access_token: 'fresh-token', refresh_token: 'new-refresh' }];
        });

        clientMock.onGet('/protected').reply((config) =>
        {
            if (config.headers?.Authorization === 'Bearer expired-token')
            {
                return [200, { success: false, message: 'יש להתחבר מחדש', error: 'unauthorized' }];
            }
            return [200, { success: true, message: 'ok' }];
        });

        const [a, b, c] = await Promise.all([
            axiosClient.get('/protected'),
            axiosClient.get('/protected'),
            axiosClient.get('/protected'),
        ]);

        expect(a.data.success).toBe(true);
        expect(b.data.success).toBe(true);
        expect(c.data.success).toBe(true);
        expect(refreshCalls).toBe(1);
    });

    it('clears stored tokens and redirects when the refresh call itself fails', async () =>
    {
        webTokenStorage.setAccessToken('expired-token');
        webTokenStorage.setRefreshToken('also-invalid');

        refreshMock.onPost(/\/api\/auth\/refresh$/).reply(200, {
            success: false, message: 'ההתחברות פגה, יש להתחבר מחדש', error: 'session_not_found',
        });
        clientMock.onGet('/protected').reply(200, {
            success: false, message: 'יש להתחבר מחדש', error: 'unauthorized',
        });

        const res = await axiosClient.get('/protected');

        // Resolves (never throws) with the original failed response, so
        // every caller can use the same `if (!res.data.success)` pattern
        // regardless of whether a refresh was attempted behind the scenes.
        expect(res.data.success).toBe(false);
        expect(webTokenStorage.clear).toHaveBeenCalledTimes(1);
        expect(window.location.href).toBe('/login');
    });

    it('clears tokens when the refresh call fails at the network level', async () =>
    {
        webTokenStorage.setAccessToken('expired-token');
        webTokenStorage.setRefreshToken('also-invalid');

        refreshMock.onPost(/\/api\/auth\/refresh$/).networkError();
        clientMock.onGet('/protected').reply(200, {
            success: false, message: 'יש להתחבר מחדש', error: 'unauthorized',
        });

        const res = await axiosClient.get('/protected');

        expect(res.data.success).toBe(false);
        expect(webTokenStorage.clear).toHaveBeenCalledTimes(1);
    });

    it('does not attempt a refresh loop for a second unauthorized response on the retried request', async () =>
    {
        webTokenStorage.setAccessToken('always-expired');
        webTokenStorage.setRefreshToken('valid-refresh');

        let refreshCalls = 0;
        refreshMock.onPost(/\/api\/auth\/refresh$/).reply(() =>
        {
            refreshCalls += 1;
            return [200, { success: true, message: 'ok', access_token: 'still-bad-token', refresh_token: 'new-refresh' }];
        });
        clientMock.onGet('/always-unauthorized').reply(200, {
            success: false, message: 'יש להתחבר מחדש', error: 'unauthorized',
        });

        const res = await axiosClient.get('/always-unauthorized');

        expect(res.data.success).toBe(false);
        expect(refreshCalls).toBe(1);
    });

    // Regression coverage for a real bug found while testing the OLD
    // status-code-based interceptor: making /api/auth/refresh itself respond
    // with an auth failure recursed back through the same interceptor and
    // deadlocked, because nothing special-cased "this request IS the
    // refresh call." The new error-CODE-based design (`error ===
    // 'unauthorized'`) is structurally immune to that: /api/auth/refresh's own
    // failure responses use codes like `session_not_found` /
    // `invalid_token`, never `unauthorized` (that code only ever comes
    // from the `authenticate` middleware, which /api/auth/refresh doesn't go
    // through), so this can no longer recurse.
    it('does not deadlock when /api/auth/refresh responds with a non-"unauthorized" failure', async () =>
    {
        webTokenStorage.setAccessToken('expired-token');
        webTokenStorage.setRefreshToken('expired-refresh-too');

        refreshMock.onPost(/\/api\/auth\/refresh$/).reply(200, {
            success: false, message: 'ההתחברות פגה, יש להתחבר מחדש', error: 'session_expired',
        });
        clientMock.onGet('/protected').reply(200, {
            success: false, message: 'יש להתחבר מחדש', error: 'unauthorized',
        });

        const res = await axiosClient.get('/protected');

        expect(res.data.success).toBe(false);
        expect(webTokenStorage.clear).toHaveBeenCalledTimes(1);
    });
});
