import axios from 'axios';
import type { AxiosInstance } from 'axios';
import type { AuthUser } from '../types/auth';

// Abstracts "where tokens live" per platform, passed in by the caller (same
// DI pattern as createAuthApi(client)) — this file never touches
// SecureStore/sessionStorage/localStorage directly. See shared/README.md
// Convention 2.
export interface ApiTokenStorage
{
    // Sync read — must be safe to call from the request interceptor on
    // every outgoing request.
    getAccessToken():  string | null;
    getRefreshToken(): Promise<string | null> | string | null;
    // Called with the freshly-rotated tokens after a successful refresh.
    // Mobile just persists them; web also mutates its axios instance's
    // default Authorization header — see that platform's client file for
    // why.
    applyRefreshedTokens(access: string, refresh: string): Promise<void> | void;
    clear(): Promise<void> | void;
}

// Was two independent ~85-line copies (mobile/src/api/axios.ts,
// web/src/api/client.ts) of the same request/response interceptor wiring
// and single-flight refresh dedup — see APP/review.md finding 2.1.
//
// The backend always answers HTTP 200; success/failure lives in the
// response body (`{success, message, error?}`). Axios therefore never
// rejects for business-logic failures (wrong password, validation errors,
// blocked, ...) — only for genuine network failures. The token-refresh
// trigger has to live in the *success* handler, keyed off
// `data.error === 'unauthorized'` rather than a 401 status code.
//
// Concurrent requests that all expire at once share a single in-flight
// refresh via `refreshPromise` instead of a manual queue — every caller
// just awaits the same promise and gets the same outcome. This is also
// structurally immune to a deadlock a status-code-based version would be
// exposed to: /auth/refresh's own failure codes (session_not_found,
// session_expired, invalid_token, ...) are never `unauthorized` — that
// code only ever comes from the `authenticate` middleware, which
// /auth/refresh doesn't go through — so a failing refresh call can't
// recurse back into this same trigger.
//
// The refresh POST itself deliberately uses a raw `axios.post` rather than
// the interceptor-wired `client` returned below — mobile's original
// implementation did this to be structurally immune to any recursion
// through this same response interceptor, even though it's currently
// provably unreachable per the paragraph above; this unification keeps
// that stronger guarantee rather than relaxing it.
export function createApiClient(
    baseURL:       string,
    tokenStorage:  ApiTokenStorage,
    onAuthFailure: () => void,
): { client: AxiosInstance; performRefresh: () => Promise<AuthUser | null> }
{
    const client = axios.create({ baseURL });

    client.interceptors.request.use((config) =>
    {
        const token = tokenStorage.getAccessToken();

        if (token)
        {
            config.headers.Authorization = `Bearer ${token}`;
        }

        return config;
    });

    let refreshPromise: Promise<AuthUser | null> | null = null;

    async function performRefresh(): Promise<AuthUser | null>
    {
        if (refreshPromise)
        {
            return refreshPromise;
        }

        refreshPromise = (async () =>
        {
            try
            {
                const stored = await tokenStorage.getRefreshToken();

                if (!stored)
                {
                    return null;
                }

                const { data } = await axios.post(`${baseURL}/api/auth/refresh`, { refresh_token: stored });

                if (!data.success)
                {
                    return null;
                }

                await tokenStorage.applyRefreshedTokens(data.access_token, data.refresh_token);

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
                refreshPromise = null;
            }
        })();

        return refreshPromise;
    }

    client.interceptors.response.use(async (response) =>
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
            await tokenStorage.clear();
            onAuthFailure();
            return response;
        }

        return client(original);
    });

    return { client, performRefresh };
}
