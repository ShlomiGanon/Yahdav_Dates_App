import { useCallback, useEffect, useState } from 'react';
import { usersApi } from '../../../api/users';
import type { UserDetail, UserStatus } from '../../../types';

interface ActionResult {
  success: boolean;
  message: string;
}

export function useUser(id: string) {
  const [user, setUser]       = useState<UserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [saving, setSaving]   = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await usersApi.get(id);
      if (!data.success) {
        setError(data.message);
        return;
      }
      setUser(data);
    } catch {
      setError('שגיאה בטעינת המשתמש');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  async function updateStatus(status: UserStatus): Promise<ActionResult> {
    if (!user) return { success: false, message: 'המשתמש לא נטען' };
    setSaving(true);
    try {
      const data = await usersApi.updateStatus(id, status);
      if (data.success) {
        setUser({ ...user, status });
      }
      return { success: data.success, message: data.message };
    } catch {
      return { success: false, message: 'שגיאת רשת, נסה שוב' };
    } finally {
      setSaving(false);
    }
  }

  async function deleteUser(): Promise<ActionResult> {
    setDeleting(true);
    try {
      const data = await usersApi.delete(id);
      return { success: data.success, message: data.message };
    } catch {
      return { success: false, message: 'שגיאת רשת, נסה שוב' };
    } finally {
      setDeleting(false);
    }
  }

  return { user, loading, error, saving, deleting, updateStatus, deleteUser, reload: load };
}
