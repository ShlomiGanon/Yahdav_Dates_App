import { createApiClient } from '@shared/api/client';
import { DEFAULT_API_BASE_URL } from '@shared/config';
import { getAccessToken, getRefreshToken, saveTokens, clearTokens } from '../auth/storage';

const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL;

// Registered by AuthContext so the interceptor can trigger a logout
// without importing AuthContext (avoids circular dependency)
let authFailureCallback: (() => void) | null = null;
export function setOnAuthFailure(cb: () => void): void {
  authFailureCallback = cb;
}

const { client, performRefresh, setBaseURL } = createApiClient(
  BASE_URL,
  {
    getAccessToken,
    getRefreshToken,
    applyRefreshedTokens: saveTokens,
    clear: clearTokens,
  },
  () => authFailureCallback?.(),
);

export const api = client;
export { performRefresh, setBaseURL };
