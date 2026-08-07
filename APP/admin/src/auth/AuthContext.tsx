import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { authApi } from '../api/auth';
import { performRefresh } from '../api/axios';
import { tokenStore } from '../api/tokenStore';
import type { AdminUser } from '../types';

// Every server call resolves — success or failure is `{success, message}`,
// never a thrown error (except for genuine network failures, which axios
// still rejects). Callers read `.success`/`.message` directly instead of
// try/catch, matching the backend's always-200 contract.
export interface AuthResult {
  success: boolean;
  message: string;
}

interface AuthState {
  user: AdminUser | null;
  loading: boolean;
  login: (identifier: string, password: string) => Promise<AuthResult>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]       = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Clears every trace of a session — used both for an explicit logout and
  // for a restored-but-not-admin session (see the effect below). Keeps
  // user null in every case this app cares about: is_admin is checked here
  // once, centrally, rather than at every place that reads `user`.
  const clearSession = useCallback(async (refreshToken: string | null) => {
    if (refreshToken) await authApi.logout(refreshToken).catch(() => {});
    tokenStore.set(null);
    localStorage.removeItem('refresh_token');
    setUser(null);
  }, []);

  // On mount: try to restore session from stored refresh token. Goes
  // through the shared performRefresh() dedup (see api/axios.ts) rather
  // than calling authApi.refresh() directly — see that function's comment
  // for why (single-use refresh tokens + React StrictMode double-invoke).
  useEffect(() => {
    const storedRefresh = localStorage.getItem('refresh_token');
    if (!storedRefresh) { setLoading(false); return; }

    performRefresh()
      .then((refreshedUser) => {
        if (!refreshedUser)
        {
          localStorage.removeItem('refresh_token');
          return;
        }

        // is_admin comes back fresh from the DB on every refresh (see
        // backend/src/routes/auth.routes.ts) — login() already refuses a
        // non-admin at sign-in, but a *restored* session doesn't go
        // through that gate on its own, so it's enforced here instead.
        // performRefresh() already persisted the rotated tokens via
        // applyRefreshedTokens before this runs, regardless of is_admin —
        // clearSession reads the (now-rotated) stored refresh token back
        // out to revoke it properly rather than leaving it live.
        if (!refreshedUser.is_admin)
        {
          clearSession(localStorage.getItem('refresh_token'));
          return;
        }

        setUser(refreshedUser);
      })
      .finally(() => setLoading(false));
  }, [clearSession]);

  const login = useCallback(async (identifier: string, password: string): Promise<AuthResult> => {
    const data = await authApi.login(identifier, password);

    if (!data.success) {
      return { success: false, message: data.message };
    }
    if (!data.is_admin) {
      return { success: false, message: 'משתמש זה אינו מנהל מערכת.' };
    }

    tokenStore.set(data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    setUser({ user_id: data.user_id, email: data.email, username: data.username, is_admin: data.is_admin });

    return { success: true, message: data.message };
  }, []);

  const logout = useCallback(async () => {
    await clearSession(localStorage.getItem('refresh_token'));
  }, [clearSession]);

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
