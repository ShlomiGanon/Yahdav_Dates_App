import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = 'dev_server_url';

// Not a secret (unlike the tokens in auth/storage.ts, which use
// SecureStore) — just a locally-remembered address, so AsyncStorage is
// the right fit. Only used by the dev-build server-URL gate (see
// components/ServerUrlGate.tsx).
export async function saveServerUrl(url: string): Promise<void>
{
    await AsyncStorage.setItem(KEY, url);
}

export async function loadServerUrl(): Promise<string | null>
{
    return AsyncStorage.getItem(KEY);
}
