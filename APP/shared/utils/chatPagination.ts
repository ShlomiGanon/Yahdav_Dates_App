// Chat message pagination — was two independent copies of the same
// PAGE_SIZE constant and "did this page come back full, so there might be
// more" heuristic, in mobile's hooks/useMessages.ts and web's
// ChatMasterDetail.tsx. See APP/review.md finding 2.11.
export const CHAT_PAGE_SIZE = 20;

export function hasMorePages(receivedCount: number): boolean
{
    return receivedCount === CHAT_PAGE_SIZE;
}
