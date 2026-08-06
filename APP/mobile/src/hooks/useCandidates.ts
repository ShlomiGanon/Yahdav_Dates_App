import { useEffect, useState } from 'react';
import { usersApi } from '../api/users';
import { DISCOVER_PAGE_SIZE, hasMoreCandidates } from '@shared/utils/discoverPagination';
import { clientMessage } from '@shared/copy/client';
import type { Candidate } from '../types/user';

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
      const data = await usersApi.discoverCandidates(pageNum, DISCOVER_PAGE_SIZE);
      if (!data.success) {
        setError(data.message);
        return;
      }
      if (initial) setCandidates(data.candidates);
      else setCandidates((prev) => [...prev, ...data.candidates]);
      setHasMore(hasMoreCandidates(data.candidates.length));
      setPage(pageNum);
      setError('');
    } catch {
      setError(clientMessage('load_candidates_failed'));
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
