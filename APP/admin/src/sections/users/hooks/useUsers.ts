import { useCallback, useEffect, useState } from 'react';
import { usersApi } from '../../../api/users';
import type { UserSummary } from '../../../types';

const PAGE_SIZE = 20;

export function useUsers() {
  const [users, setUsers]       = useState<UserSummary[]>([]);
  const [total, setTotal]       = useState(0);
  const [page, setPage]         = useState(1);
  const [search, setSearch]     = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const fetch = useCallback(async (p: number, q: string) => {
    setLoading(true);
    setError('');
    try {
      const data = await usersApi.list({
        limit:  PAGE_SIZE,
        offset: (p - 1) * PAGE_SIZE,
        ...(q ? { search: q } : {}),
      });
      if (!data.success) {
        setError(data.message);
        return;
      }
      setUsers(data.users);
      setTotal(data.total);
    } catch {
      setError('שגיאה בטעינת המשתמשים');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch(page, search);
  }, [fetch, page, search]);

  function handleSearch(q: string) {
    setSearch(q);
    setPage(1);
  }

  function handlePage(p: number) {
    setPage(Math.max(1, Math.min(p, totalPages)));
  }

  function refresh() {
    fetch(page, search);
  }

  return { users, total, page, totalPages, search, loading, error, setSearch: handleSearch, setPage: handlePage, refresh };
}
