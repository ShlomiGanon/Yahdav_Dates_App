import React, { createContext, useContext, ReactNode, useEffect } from 'react';
import { api, setOnAuthFailure } from '../api/axios';
import { usersApi } from '../api/users';
import { saveTokens, clearTokens, getRefreshToken } from './storage';
import { useAutoLogin } from './useAutoLogin';

type User = {
  user_id: string;
  email:    string;
  username: string;
  is_admin: boolean;
};

type AuthContextValue = {
  user:      User | null;
  isLoading: boolean;
  login:     (identifier: string, password: string) => Promise<void>;
  logout:    () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { user, setUser, isLoading } = useAutoLogin();

  useEffect(() => {
    setOnAuthFailure(() => setUser(null));
  }, [setUser]);

  const login = async (identifier: string, password: string): Promise<void> => {
    const { data } = await api.post('/auth/login', { identifier, password });
    await saveTokens(data.access_token, data.refresh_token);
    setUser(data.user ?? data);
  };

  const logout = async (): Promise<void> => {
    try {
      const refresh_token = await getRefreshToken();
      await Promise.all([
        api.post('/auth/logout', { refresh_token }),
        usersApi.unregisterPushToken().catch(() => {}),
      ]);
    } finally {
      await clearTokens();
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
