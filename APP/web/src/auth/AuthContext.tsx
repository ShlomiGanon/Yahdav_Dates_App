import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { authApi, axiosClient, performRefresh } from '../api/client';
import { webTokenStorage }       from './storage';
import type { AuthUser }         from '@shared/types/auth';

// Every server call resolves — success or failure is `{success, message}`,
// never a thrown error (except for genuine network failures, which axios
// still rejects). Callers read `.success`/`.message` directly instead of
// try/catch, matching the backend's always-200 contract.
export interface AuthResult
{
    success: boolean;
    message: string;
}

interface AuthState
{
    user:    AuthUser | null;
    loading: boolean;
    login:   (identifier: string, password: string) => Promise<AuthResult>;
    signup:  (email: string, username: string, password: string) => Promise<AuthResult>;
    logout:  () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

function extractUser(u: AuthUser): AuthUser
{
    return { user_id: u.user_id, email: u.email, username: u.username, is_admin: u.is_admin };
}

export function AuthProvider({ children }: { children: ReactNode })
{
    const [user,    setUser]    = useState<AuthUser | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() =>
    {
        const stored = webTokenStorage.getRefreshToken();

        if (!stored)
        {
            setLoading(false);
            return;
        }

        // Goes through the shared performRefresh() dedup (see api/client.ts)
        // rather than calling authApi.refresh() directly — refresh tokens
        // are single-use, so two concurrent calls with the same stored token
        // (e.g. React StrictMode double-invoking this effect in dev) would
        // otherwise race and the loser could clear a session the winner just
        // established.
        performRefresh()
            .then((refreshedUser) =>
            {
                if (!refreshedUser)
                {
                    webTokenStorage.clear();
                    return;
                }

                setUser(refreshedUser);
            })
            .finally(() => setLoading(false));
    }, []);

    async function login(identifier: string, password: string): Promise<AuthResult>
    {
        const res = await authApi.login(identifier, password);

        if (!res.success)
        {
            return { success: false, message: res.message };
        }

        webTokenStorage.setAccessToken(res.access_token);
        webTokenStorage.setRefreshToken(res.refresh_token);
        axiosClient.defaults.headers.common.Authorization =
            `Bearer ${res.access_token}`;
        setUser(extractUser(res));

        return { success: true, message: res.message };
    }

    async function signup(email: string, username: string, password: string): Promise<AuthResult>
    {
        const res = await authApi.signup(email, username, password);

        return { success: res.success, message: res.message };
    }

    async function logout(): Promise<void>
    {
        const stored = webTokenStorage.getRefreshToken();

        if (stored)
        {
            await authApi.logout(stored).catch(() =>
            {
                // clear locally even if the server call fails
            });
        }

        webTokenStorage.clear();
        delete axiosClient.defaults.headers.common.Authorization;
        setUser(null);
    }

    return (
        <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth(): AuthState
{
    const ctx = useContext(AuthContext);

    if (!ctx)
    {
        throw new Error('useAuth must be used inside AuthProvider');
    }

    return ctx;
}
