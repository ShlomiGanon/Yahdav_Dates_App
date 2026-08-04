import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { authApi, axiosClient }  from '../api/client';
import { webTokenStorage }       from './storage';
import type { AuthUser }         from '@shared/types/auth';

interface AuthState
{
    user:    AuthUser | null;
    loading: boolean;
    login:   (identifier: string, password: string) => Promise<void>;
    logout:  () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

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

        authApi
            .refresh(stored)
            .then((tokens) =>
            {
                webTokenStorage.setAccessToken(tokens.access_token);
                webTokenStorage.setRefreshToken(tokens.refresh_token);
                axiosClient.defaults.headers.common.Authorization =
                    `Bearer ${tokens.access_token}`;
                return authApi.me();
            })
            .then((u) => setUser(u))
            .catch(() => webTokenStorage.clear())
            .finally(() => setLoading(false));
    }, []);

    async function login(identifier: string, password: string): Promise<void>
    {
        const tokens = await authApi.login(identifier, password);

        webTokenStorage.setAccessToken(tokens.access_token);
        webTokenStorage.setRefreshToken(tokens.refresh_token);
        axiosClient.defaults.headers.common.Authorization =
            `Bearer ${tokens.access_token}`;

        const u = await authApi.me();
        setUser(u);
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
        <AuthContext.Provider value={{ user, loading, login, logout }}>
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
