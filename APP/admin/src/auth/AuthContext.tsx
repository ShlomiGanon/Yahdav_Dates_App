import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { api } from '../api/axios';
import { authApi } from '../api/auth';
import { tokenStore } from '../api/tokenStore';
import type { AdminUser } from '../types';

interface AuthState {
  user: AdminUser | null;
  loading: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]       = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount: try to restore session from stored refresh token
  useEffect(() => {
    const storedRefresh = localStorage.getItem('refresh_token');
    if (!storedRefresh) { setLoading(false); return; }

    api
      .post<{ access_token: string; refresh_token: string; user_id: string; email: string; username: string; is_admin: boolean }>(
        '/auth/refresh',
        { refresh_token: storedRefresh },
      )
      .then((r) => {
        tokenStore.set(r.data.access_token);
        localStorage.setItem('refresh_token', r.data.refresh_token);
        setUser({
          user_id:  r.data.user_id,
          email:    r.data.email,
          username: r.data.username,
          is_admin: r.data.is_admin,
        });
      })
      .catch(() => {
        localStorage.removeItem('refresh_token');
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (identifier: string, password: string) => {
    const data = await authApi.login(identifier, password);
    if (!data.is_admin) throw new Error('not_admin');
    tokenStore.set(data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    setUser({ user_id: data.user_id, email: data.email, username: data.username, is_admin: data.is_admin });
  }, []);

  const logout = useCallback(async () => {
    const storedRefresh = localStorage.getItem('refresh_token');
    if (storedRefresh) await authApi.logout(storedRefresh);
    tokenStore.set(null);
    localStorage.removeItem('refresh_token');
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
