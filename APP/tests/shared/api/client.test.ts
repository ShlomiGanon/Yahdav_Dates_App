import axios from 'axios';
import { createApiClient } from '../../../shared/api/client';
import type { ApiTokenStorage } from '../../../shared/api/client';

// Pins the concurrent-refresh race specifically: N overlapping calls while
// a refresh is in flight must all resolve to the SAME outcome from ONE
// underlying network call, not N separate racing calls — and the guard
// must reset correctly afterward so a later refresh isn't permanently
// stuck. Was verified against a local reference implementation of the
// dedup pattern before createApiClient existed (see APP/review.md finding
// 2.1 for that pinning pass); these are the same assertions, now run
// against the real export's performRefresh.
describe('createApiClient — concurrent-refresh race', () =>
{
    function fakeTokenStorage(refreshToken: string | null = 'stored-refresh-token'): ApiTokenStorage
    {
        return {
            getAccessToken:  () => null,
            getRefreshToken: () => refreshToken,
            applyRefreshedTokens: jest.fn(),
            clear: jest.fn(),
        };
    }

    afterEach(() =>
    {
        jest.restoreAllMocks();
    });

    it('dedupes N concurrent calls into exactly one underlying network call', async () =>
    {
        let resolveCall: (value: unknown) => void;
        const pending = new Promise((resolve) => { resolveCall = resolve; });
        const postSpy = jest.spyOn(axios, 'post').mockReturnValue(pending as Promise<unknown>);

        const { performRefresh } = createApiClient('http://api.test', fakeTokenStorage(), jest.fn());

        const p1 = performRefresh();
        const p2 = performRefresh();
        const p3 = performRefresh();

        // createApiClient awaits tokenStorage.getRefreshToken() before
        // calling axios.post (needed since mobile's getRefreshToken is
        // genuinely async via SecureStore) — one microtask tick for that
        // to flush before the underlying call count is observable.
        await Promise.resolve();
        expect(postSpy).toHaveBeenCalledTimes(1);

        resolveCall!({
            data: {
                success: true, access_token: 'new-access', refresh_token: 'new-refresh',
                user_id: 'u1', email: 'a@b.com', username: 'a', is_admin: false,
            },
        });

        const [r1, r2, r3] = await Promise.all([p1, p2, p3]);

        expect(postSpy).toHaveBeenCalledTimes(1);
        expect(r1).toEqual(r2);
        expect(r2).toEqual(r3);
        expect(r1).toEqual({ user_id: 'u1', email: 'a@b.com', username: 'a', is_admin: false });
    });

    it('allows a fresh refresh after the previous one completed (not permanently deduped)', async () =>
    {
        const postSpy = jest.spyOn(axios, 'post')
            .mockResolvedValueOnce({ data: { success: true, user_id: 'u1', email: 'a@b.com', username: 'a', is_admin: false } })
            .mockResolvedValueOnce({ data: { success: true, user_id: 'u2', email: 'c@d.com', username: 'c', is_admin: false } });

        const { performRefresh } = createApiClient('http://api.test', fakeTokenStorage(), jest.fn());

        const first  = await performRefresh();
        const second = await performRefresh();

        expect(postSpy).toHaveBeenCalledTimes(2);
        expect(first).toEqual({ user_id: 'u1', email: 'a@b.com', username: 'a', is_admin: false });
        expect(second).toEqual({ user_id: 'u2', email: 'c@d.com', username: 'c', is_admin: false });
    });

    it('a failed (thrown) refresh clears the in-flight guard so a retry can happen', async () =>
    {
        const postSpy = jest.spyOn(axios, 'post')
            .mockRejectedValueOnce(new Error('network down'))
            .mockResolvedValueOnce({ data: { success: true, user_id: 'u1', email: 'a@b.com', username: 'a', is_admin: false } });

        const { performRefresh } = createApiClient('http://api.test', fakeTokenStorage(), jest.fn());

        const first = await performRefresh();
        expect(first).toBeNull();

        const second = await performRefresh();
        expect(second).toEqual({ user_id: 'u1', email: 'a@b.com', username: 'a', is_admin: false });
        expect(postSpy).toHaveBeenCalledTimes(2);
    });

    it('a refresh that resolves with success:false resolves all waiters to null, not throwing', async () =>
    {
        const postSpy = jest.spyOn(axios, 'post').mockResolvedValue({ data: { success: false } });

        const { performRefresh } = createApiClient('http://api.test', fakeTokenStorage(), jest.fn());

        const [r1, r2] = await Promise.all([performRefresh(), performRefresh()]);

        expect(r1).toBeNull();
        expect(r2).toBeNull();
        expect(postSpy).toHaveBeenCalledTimes(1);
    });

    it('a later, independent call after the first resolved gets a fresh result, not a stale cached one', async () =>
    {
        const postSpy = jest.spyOn(axios, 'post')
            .mockResolvedValueOnce({ data: { success: true, user_id: 'u1', email: 'a@b.com', username: 'a', is_admin: false } });

        const { performRefresh } = createApiClient('http://api.test', fakeTokenStorage(), jest.fn());
        await performRefresh();

        postSpy.mockResolvedValueOnce({ data: { success: true, user_id: 'u2', email: 'c@d.com', username: 'c', is_admin: false } });
        const second = await performRefresh();

        expect(second).toEqual({ user_id: 'u2', email: 'c@d.com', username: 'c', is_admin: false });
    });

    it('returns null and never calls the network when no refresh token is stored', async () =>
    {
        const postSpy = jest.spyOn(axios, 'post');
        const { performRefresh } = createApiClient('http://api.test', fakeTokenStorage(null), jest.fn());

        const result = await performRefresh();

        expect(result).toBeNull();
        expect(postSpy).not.toHaveBeenCalled();
    });

    it('calls tokenStorage.applyRefreshedTokens with the new tokens on success', async () =>
    {
        jest.spyOn(axios, 'post').mockResolvedValue({
            data: { success: true, access_token: 'new-access', refresh_token: 'new-refresh', user_id: 'u1', email: 'a@b.com', username: 'a', is_admin: false },
        });
        const storage = fakeTokenStorage();

        const { performRefresh } = createApiClient('http://api.test', storage, jest.fn());
        await performRefresh();

        expect(storage.applyRefreshedTokens).toHaveBeenCalledWith('new-access', 'new-refresh');
    });
});

// Pins setBaseURL — added for mobile's dev-build runtime server-URL gate
// (see mobile/src/components/ServerUrlGate.tsx). Only mobile ever calls
// this; web and admin's baseURL never changes after construction.
describe('createApiClient — setBaseURL', () =>
{
    function fakeTokenStorage(refreshToken: string | null = 'stored-refresh-token'): ApiTokenStorage
    {
        return {
            getAccessToken:  () => null,
            getRefreshToken: () => refreshToken,
            applyRefreshedTokens: jest.fn(),
            clear: jest.fn(),
        };
    }

    afterEach(() =>
    {
        jest.restoreAllMocks();
    });

    it('updates client.defaults.baseURL', () =>
    {
        const { client, setBaseURL } = createApiClient('http://old.test', fakeTokenStorage(), jest.fn());

        expect(client.defaults.baseURL).toBe('http://old.test');

        setBaseURL('http://new.test');

        expect(client.defaults.baseURL).toBe('http://new.test');
    });

    // The bug setBaseURL exists to fix: performRefresh's raw axios.post
    // call closes over the baseURL *parameter*, entirely separate from
    // client.defaults.baseURL. A setBaseURL that only touched the client's
    // defaults would leave this call silently posting to the old server
    // forever.
    it('performRefresh posts to the new URL after setBaseURL is called, not the old one', async () =>
    {
        const postSpy = jest.spyOn(axios, 'post').mockResolvedValue({
            data: { success: true, access_token: 'a', refresh_token: 'r', user_id: 'u1', email: 'a@b.com', username: 'a', is_admin: false },
        });

        const { performRefresh, setBaseURL } = createApiClient('http://old.test', fakeTokenStorage(), jest.fn());

        setBaseURL('http://new.test');
        await performRefresh();

        expect(postSpy).toHaveBeenCalledWith('http://new.test/api/auth/refresh', expect.anything());
        expect(postSpy).not.toHaveBeenCalledWith('http://old.test/api/auth/refresh', expect.anything());
    });

    it('a refresh already in flight when setBaseURL is called still resolves normally (no crash, no lost update)', async () =>
    {
        let resolveCall: (value: unknown) => void;
        const pending = new Promise((resolve) => { resolveCall = resolve; });
        jest.spyOn(axios, 'post').mockReturnValue(pending as Promise<unknown>);

        const { performRefresh, setBaseURL } = createApiClient('http://old.test', fakeTokenStorage(), jest.fn());

        const inFlight = performRefresh();
        await Promise.resolve();
        setBaseURL('http://new.test');

        resolveCall!({
            data: { success: true, access_token: 'a', refresh_token: 'r', user_id: 'u1', email: 'a@b.com', username: 'a', is_admin: false },
        });

        await expect(inFlight).resolves.toEqual({ user_id: 'u1', email: 'a@b.com', username: 'a', is_admin: false });
    });
});
