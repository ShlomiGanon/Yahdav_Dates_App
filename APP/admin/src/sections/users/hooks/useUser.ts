import { useCallback, useEffect, useState } from 'react';
import { usersApi } from '../../../api/users';
import type { UserDetail, UserStatus } from '../../../types';

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
      setUser(data);
    } catch {
      setError('שגיאה בטעינת המשתמש');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  async function updateStatus(status: UserStatus): Promise<void> {
    if (!user) return;
    setSaving(true);
    try {
      await usersApi.updateStatus(id, status);
      setUser({ ...user, status });
    } finally {
      setSaving(false);
    }
  }

  async function deleteUser(): Promise<void> {
    setDeleting(true);
    try {
      await usersApi.delete(id);
    } finally {
      setDeleting(false);
    }
  }

  return { user, loading, error, saving, deleting, updateStatus, deleteUser };
}
