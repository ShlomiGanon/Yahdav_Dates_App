import { useEffect, useState } from 'react';
import { usersApi } from '../api/users';
import type { Candidate } from '../types/user';

const PAGE_SIZE = 20;

export function useCandidates() {
  const [candidates,  setCandidates]  = useState<Candidate[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore,     setHasMore]     = useState(true);
  const [page,        setPage]        = useState(1);
  const [error,       setError]       = useState('');

  useEffect(() => { loadPage(1, true); }, []);

  const loadPage = async (pageNum: number, initial = false) => {
    if (initial) setLoading(true);
    else setLoadingMore(true);
    try {
      const data = await usersApi.discoverCandidates(pageNum, PAGE_SIZE);
      if (!data.success) {
        setError(data.message);
        return;
      }
      if (initial) setCandidates(data.candidates);
      else setCandidates((prev) => [...prev, ...data.candidates]);
      setHasMore(data.candidates.length === PAGE_SIZE);
      setPage(pageNum);
      setError('');
    } catch {
      setError('טעינת האנשים נכשלה. אנא נסה/י שוב מאוחר יותר.');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  const loadMore = () => {
    if (!loadingMore && !loading && hasMore) loadPage(page + 1);
  };

  return { candidates, loading, loadingMore, error, loadMore };
}
