import { useState, useEffect } from 'react';
import { api } from '../api/axios';
import { loadTokens, clearTokens } from './storage';
import type { ApiEnvelope } from '../types/api';

type User = {
  user_id: string;
  email:    string;
  username: string;
  is_admin: boolean;
};

// Handles boot-time token rehydration — checks SecureStore and validates
// the stored session against the backend on every app launch.
//
// The backend always answers HTTP 200; a genuinely invalid/expired session
// resolves normally as {success:false}, while a pure network failure (the
// device is offline, the server is unreachable) still makes axios reject —
// there's no HTTP response at all. That distinction matters: only a
// server-confirmed invalid session should clear the stored refresh token.
// A network blip at cold boot must not silently log the user out.
export function useAutoLogin() {
  const [user,      setUser]      = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [offline,   setOffline]   = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { access, refresh } = await loadTokens();
        if (access && refresh) {
          const { data } = await api.get<ApiEnvelope & User>('/api/auth/me');
          if (data.success) {
            setUser({ user_id: data.user_id, email: data.email, username: data.username, is_admin: data.is_admin });
          } else {
            await clearTokens();
          }
        }
      } catch {
        // Network-level failure — the request never reached the server, so
        // we can't know whether the session is actually invalid. Keep the
        // stored tokens and let the user retry instead of forcing a
        // re-login.
        setOffline(true);
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  return { user, setUser, isLoading, offline };
}
