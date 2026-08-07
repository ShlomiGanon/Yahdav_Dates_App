import React, { createContext, useContext, ReactNode, useEffect } from 'react';
import { api, setOnAuthFailure } from '../api/axios';
import { usersApi } from '../api/users';
import { saveTokens, clearTokens, getRefreshToken } from './storage';
import { useAutoLogin } from './useAutoLogin';
import type { ApiEnvelope } from '../types/api';

type User = {
  user_id: string;
  email:    string;
  username: string;
  is_admin: boolean;
};

// Every server call resolves — success or failure is `{success, message}`,
// never a thrown error (except for genuine network failures, which axios
// still rejects). Callers read `.success`/`.message` directly instead of
// try/catch, matching the backend's always-200 contract.
export type AuthResult = {
  success: boolean;
  message: string;
};

type AuthTokensUser = ApiEnvelope & User & { access_token: string; refresh_token: string };

type AuthContextValue = {
  user:      User | null;
  isLoading: boolean;
  offline:   boolean;
  login:     (identifier: string, password: string) => Promise<AuthResult>;
  signup:    (email: string, username: string, password: string) => Promise<AuthResult>;
  logout:    () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function extractUser(u: User): User {
  return { user_id: u.user_id, email: u.email, username: u.username, is_admin: u.is_admin };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const { user, setUser, isLoading, offline } = useAutoLogin();

  useEffect(() => {
    setOnAuthFailure(() => setUser(null));
  }, [setUser]);

  const login = async (identifier: string, password: string): Promise<AuthResult> => {
    const { data } = await api.post<AuthTokensUser>('/api/auth/login', { identifier, password });

    if (!data.success) {
      return { success: false, message: data.message };
    }

    await saveTokens(data.access_token, data.refresh_token);
    setUser(extractUser(data));

    return { success: true, message: data.message };
  };

  const signup = async (email: string, username: string, password: string): Promise<AuthResult> => {
    const { data } = await api.post<ApiEnvelope & User>('/api/auth/signup', { email, username, password });

    return { success: data.success, message: data.message };
  };

  const logout = async (): Promise<void> => {
    try {
      const refresh_token = await getRefreshToken();
      await Promise.all([
        api.post('/api/auth/logout', { refresh_token }),
        usersApi.unregisterPushToken().catch(() => {}),
      ]);
    } finally {
      await clearTokens();
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, offline, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
