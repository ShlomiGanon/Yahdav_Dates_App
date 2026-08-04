import axios from 'axios';
import { createAuthApi }  from '@shared/api/auth';
import { createUsersApi } from '@shared/api/users';
import { createChatApi }  from '@shared/api/chat';
import { webTokenStorage } from '../auth/storage';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:3000';

export const axiosClient = axios.create({ baseURL: BASE_URL });

// ── Request interceptor — attach current access token ─────────────────────
axiosClient.interceptors.request.use((config) =>
{
    const token = webTokenStorage.getAccessToken();

    if (token)
    {
        config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
});

// ── Response interceptor — auto-refresh on {success:false, error:'unauthorized'} ──
// The backend always answers with HTTP 200; success/failure lives in the
// response body. Axios therefore never rejects for business-logic failures
// (wrong password, validation errors, etc.) — only for genuine network
// failures. The token-refresh trigger has to live in the *success* handler,
// keyed off `response.data.error === 'unauthorized'` rather than a 401
// status code.
//
// Concurrent requests that all expire at once share a single in-flight
// refresh via `_refreshPromise` instead of queueing manually — every caller
// just awaits the same promise and gets the same true/false outcome.
let _refreshPromise: Promise<boolean> | null = null;

async function performRefresh(): Promise<boolean>
{
    if (_refreshPromise)
    {
        return _refreshPromise;
    }

    _refreshPromise = (async () =>
    {
        try
        {
            const stored = webTokenStorage.getRefreshToken();
            if (!stored)
            {
                return false;
            }

            const { data } = await axiosClient.post('/auth/refresh', { refresh_token: stored });
            if (!data.success)
            {
                return false;
            }

            webTokenStorage.setAccessToken(data.access_token);
            webTokenStorage.setRefreshToken(data.refresh_token);
            axiosClient.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
            return true;
        }
        catch
        {
            return false;
        }
        finally
        {
            _refreshPromise = null;
        }
    })();

    return _refreshPromise;
}

axiosClient.interceptors.response.use(async (response) =>
{
    const original = response.config as typeof response.config & { _retry?: boolean };
    const isUnauthorized = response.data?.success === false && response.data?.error === 'unauthorized';

    if (!isUnauthorized || original._retry)
    {
        return response;
    }

    original._retry = true;
    const refreshed = await performRefresh();

    if (!refreshed)
    {
        webTokenStorage.clear();
        window.location.href = '/login';
        return response;
    }

    return axiosClient(original);
});

// ── Typed API singletons ──────────────────────────────────────────────────
export const authApi  = createAuthApi(axiosClient);
export const usersApi = createUsersApi(axiosClient);
export const chatApi  = createChatApi(axiosClient);
