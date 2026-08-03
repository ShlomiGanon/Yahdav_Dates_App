import * as SecureStore from 'expo-secure-store';

const KEY_ACCESS  = 'access_token';
const KEY_REFRESH = 'refresh_token';

// In-memory cache so the axios interceptor can read synchronously
let _accessToken: string | null = null;

export async function saveTokens(access: string, refresh: string): Promise<void> {
  _accessToken = access;
  await SecureStore.setItemAsync(KEY_ACCESS,  access);
  await SecureStore.setItemAsync(KEY_REFRESH, refresh);
}

export async function loadTokens(): Promise<{ access: string | null; refresh: string | null }> {
  const access  = await SecureStore.getItemAsync(KEY_ACCESS);
  const refresh = await SecureStore.getItemAsync(KEY_REFRESH);
  _accessToken = access;
  return { access, refresh };
}

// Sync read — safe to call from the axios request interceptor
export function getAccessToken(): string | null {
  return _accessToken;
}

export async function getRefreshToken(): Promise<string | null> {
  return SecureStore.getItemAsync(KEY_REFRESH);
}

export async function clearTokens(): Promise<void> {
  _accessToken = null;
  await SecureStore.deleteItemAsync(KEY_ACCESS);
  await SecureStore.deleteItemAsync(KEY_REFRESH);
}
