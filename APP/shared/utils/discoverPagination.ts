// Discover-candidates pagination — was two independent copies of the same
// PAGE_SIZE constant and "did this page come back full, so there might be
// more" heuristic, in mobile's hooks/useCandidates.ts and
// web/src/pages/DiscoverPage.tsx. Kept as its own file rather than reused
// from shared/utils/chatPagination.ts (finding 2.11) deliberately — see
// APP/review.md Section 4's over-engineering note on this pattern group; a
// generic pagination abstraction across chat/discover/photos isn't worth
// it for three call sites with different item types.
export const DISCOVER_PAGE_SIZE = 20;

export function hasMoreCandidates(receivedCount: number): boolean
{
    return receivedCount === DISCOVER_PAGE_SIZE;
}
