import axios from 'axios';
import { createAuthApi }  from '@shared/api/auth';
import { createUsersApi } from '@shared/api/users';
import { createChatApi }  from '@shared/api/chat';
import { DEFAULT_API_BASE_URL } from '@shared/config';
import { webTokenStorage } from '../auth/storage';
import type { AuthUser } from '@shared/types/auth';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;

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
// Concurrent requests that all expire at once — and AuthContext's own
// mount-time session restore — share a single in-flight refresh via
// `_refreshPromise` instead of firing separate calls. This matters because
// refresh tokens are single-use (rotate-on-use): two concurrent calls with
// the same stored token (e.g. React StrictMode double-invoking an effect in
// dev) would otherwise race, and whichever response lands second — even the
// loser of a legitimate rotation — would clear a session the winner just
// established.
let _refreshPromise: Promise<AuthUser | null> | null = null;

export async function performRefresh(): Promise<AuthUser | null>
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
                return null;
            }

            const { data } = await axiosClient.post('/auth/refresh', { refresh_token: stored });
            if (!data.success)
            {
                return null;
            }

            webTokenStorage.setAccessToken(data.access_token);
            webTokenStorage.setRefreshToken(data.refresh_token);
            axiosClient.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
            return {
                user_id:  data.user_id,
                email:    data.email,
                username: data.username,
                is_admin: data.is_admin,
            };
        }
        catch
        {
            return null;
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
    const refreshedUser = await performRefresh();

    if (!refreshedUser)
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
