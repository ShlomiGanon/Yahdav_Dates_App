import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { RemoteImage } from '../components/RemoteImage';
import { usersApi } from '../api/client';
import { PAGE_ROUTES } from './routes';
import { formatCandidateMetaSegments, EMPTY_CANDIDATE_META_LABEL } from '@shared/utils/formatCandidateMeta';
import { DISCOVER_PAGE_SIZE, hasMoreCandidates } from '@shared/utils/discoverPagination';
import { clientMessage } from '@shared/copy/client';
import type { Candidate } from '@shared/types/user';

function metaLine(c: Candidate): string
{
    const segments = formatCandidateMetaSegments(c);
    return segments.length ? segments.join(' · ') : EMPTY_CANDIDATE_META_LABEL;
}

export function DiscoverPage()
{
    const navigate = useNavigate();

    const [candidates,  setCandidates]  = useState<Candidate[]>([]);
    const [loading,     setLoading]     = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [hasMore,     setHasMore]     = useState(true);
    const [page,        setPage]        = useState(1);
    const [error,       setError]       = useState('');
    const [selected,    setSelected]    = useState<Candidate | null>(null);

    useEffect(() =>
    {
        loadPage(1, true);
    }, []);

    async function loadPage(pageNum: number, initial = false): Promise<void>
    {
        if (initial)
        {
            setLoading(true);
        }
        else
        {
            setLoadingMore(true);
        }

        try
        {
            const data = await usersApi.discoverCandidates(pageNum, DISCOVER_PAGE_SIZE);
            if (!data.success)
            {
                setError(data.message);
                return;
            }
            setCandidates((prev) => (initial ? data.candidates : [...prev, ...data.candidates]));
            setHasMore(hasMoreCandidates(data.candidates.length));
            setPage(pageNum);
            setError('');
        }
        catch
        {
            setError(clientMessage('load_candidates_failed'));
        }
        finally
        {
            setLoading(false);
            setLoadingMore(false);
        }
    }

    function handleLoadMore(): void
    {
        if (!loadingMore && !loading && hasMore)
        {
            loadPage(page + 1);
        }
    }

    function peerProfilePath(peerId: string): string
    {
        return PAGE_ROUTES.peerProfile.replace(':peer_id', peerId);
    }

    function chatPath(peerId: string): string
    {
        return PAGE_ROUTES.chat.replace(':peer_id', peerId);
    }

    return (
        <AppShell>
            <div className="relative min-h-full">
                <div className="max-w-5xl mx-auto px-6 py-10">
                    <h1 className="text-2xl font-bold mb-6 text-white">אנשים שתרצו להכיר</h1>

                    {error && (
                        <p className="text-danger text-sm mb-4" role="alert">{error}</p>
                    )}

                    {!error && (
                        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                            {candidates.map((candidate) => (
                                <button
                                    key={candidate.user_id}
                                    type="button"
                                    onClick={() => setSelected(candidate)}
                                    className="bg-surface rounded-card overflow-hidden text-right
                                               hover:shadow-lg transition-shadow"
                                >
                                    <div className="aspect-square bg-background/10">
                                        {candidate.photo_url ? (
                                            <RemoteImage
                                                src={candidate.photo_url}
                                                className="w-full h-full object-cover"
                                            />
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center
                                                            text-secondary opacity-40 text-4xl">
                                                👤
                                            </div>
                                        )}
                                    </div>
                                    <div className="p-3">
                                        <p className="font-semibold text-secondary truncate">
                                            {candidate.name || clientMessage('unknown_user_label')}
                                        </p>
                                        <p className="text-sm text-secondary opacity-60 truncate">
                                            {metaLine(candidate)}
                                        </p>
                                    </div>
                                </button>
                            ))}

                            {!loading && candidates.length === 0 && (
                                <p className="col-span-full text-white/70 text-center py-10">
                                    עדיין אין פרופילים להצגה. חזרו מאוחר יותר 🙂
                                </p>
                            )}
                        </div>
                    )}

                    {loading && (
                        <p className="text-white/70 text-center py-10">טוען...</p>
                    )}

                    {!loading && hasMore && candidates.length > 0 && (
                        <div className="flex justify-center mt-8">
                            <button
                                type="button"
                                onClick={handleLoadMore}
                                disabled={loadingMore}
                                className="px-6 py-2 rounded-card border border-white/30 text-white/80
                                           hover:bg-white/10 disabled:opacity-50 transition-colors"
                            >
                                {loadingMore ? 'טוען עוד...' : 'טען עוד'}
                            </button>
                        </div>
                    )}
                </div>

                {selected && (
                    <>
                        <button
                            type="button"
                            aria-label={clientMessage('close_label')}
                            onClick={() => setSelected(null)}
                            className="fixed inset-0 bg-black/40 z-10"
                        />
                        <aside className="fixed top-0 bottom-0 right-0 w-full max-w-sm bg-surface z-20
                                          shadow-2xl p-6 flex flex-col gap-4 overflow-y-auto">
                            <div className="flex flex-col items-center gap-3 text-center">
                                {selected.photo_url ? (
                                    <RemoteImage
                                        src={selected.photo_url}
                                        className="w-28 h-28 rounded-full object-cover"
                                    />
                                ) : (
                                    <div className="w-28 h-28 rounded-full bg-background/10 flex items-center
                                                    justify-center text-4xl">
                                        👤
                                    </div>
                                )}
                                <h2 className="text-xl font-bold text-secondary">
                                    {selected.name || clientMessage('unknown_user_label')}
                                </h2>
                                <p className="text-secondary opacity-70">{metaLine(selected)}</p>
                            </div>

                            <button
                                type="button"
                                onClick={() => navigate(peerProfilePath(selected.user_id))}
                                className="w-full py-3 rounded-card bg-primary text-white font-semibold"
                            >
                                צפייה בפרופיל
                            </button>
                            <button
                                type="button"
                                onClick={() => navigate(chatPath(selected.user_id))}
                                className="w-full py-3 rounded-card border border-secondary text-secondary"
                            >
                                התחל שיחה
                            </button>
                            <button
                                type="button"
                                onClick={() => setSelected(null)}
                                className="w-full py-2 text-sm text-secondary underline"
                            >
                                {clientMessage('close_label')}
                            </button>
                        </aside>
                    </>
                )}
            </div>
        </AppShell>
    );
}
