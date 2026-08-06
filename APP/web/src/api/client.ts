import { createApiClient } from '@shared/api/client';
import { createAuthApi }  from '@shared/api/auth';
import { createUsersApi } from '@shared/api/users';
import { createChatApi }  from '@shared/api/chat';
import { DEFAULT_API_BASE_URL } from '@shared/config';
import { webTokenStorage } from '../auth/storage';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;

const { client, performRefresh } = createApiClient(
    BASE_URL,
    {
        getAccessToken:  webTokenStorage.getAccessToken,
        getRefreshToken: webTokenStorage.getRefreshToken,
        applyRefreshedTokens: (access, refresh) =>
        {
            webTokenStorage.setAccessToken(access);
            webTokenStorage.setRefreshToken(refresh);
            client.defaults.headers.common.Authorization = `Bearer ${access}`;
        },
        clear: webTokenStorage.clear,
    },
    // createApiClient already calls tokenStorage.clear() before invoking
    // this — matches the original single webTokenStorage.clear() call.
    () =>
    {
        window.location.href = '/login';
    },
);

export const axiosClient = client;
export { performRefresh };

// ── Typed API singletons ──────────────────────────────────────────────────
export const authApi  = createAuthApi(axiosClient);
export const usersApi = createUsersApi(axiosClient);
export const chatApi  = createChatApi(axiosClient);
