import { useState, useEffect } from 'react';
import { api } from '../api/axios';
import { loadTokens, clearTokens } from './storage';

type User = {
  user_id: string;
  email:    string;
  username: string;
  is_admin: boolean;
};

// Handles boot-time token rehydration — checks SecureStore and validates
// the stored session against the backend on every app launch.
export function useAutoLogin() {
  const [user,      setUser]      = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { access, refresh } = await loadTokens();
        if (access && refresh) {
          const { data } = await api.get<User>('/auth/me');
          setUser(data);
        }
      } catch {
        await clearTokens();
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  return { user, setUser, isLoading };
}
