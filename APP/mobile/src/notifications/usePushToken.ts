import { useEffect } from 'react';
import { useAuth } from '../auth/AuthContext';
import { setupPushNotifications } from './setup';

export function usePushToken(): void {
  const { user } = useAuth();
  useEffect(() => {
    if (!user) return;
    setupPushNotifications();
  }, [user?.user_id]);
}
