import { CHAT_PAGE_SIZE, hasMorePages } from '../../../shared/utils/chatPagination';

// Pins the pagination heuristic (`receivedCount === PAGE_SIZE`) that was
// previously duplicated as inline logic in mobile's hooks/useMessages.ts
// and web's ChatMasterDetail.tsx. Was verified against a local reference
// implementation before this file existed (see APP/review.md finding 2.11
// for that pinning pass); these are the same assertions, now run against
// the real export.
describe('hasMorePages', () =>
{
    it('reports more pages when a full page came back', () =>
    {
        expect(hasMorePages(CHAT_PAGE_SIZE)).toBe(true);
    });

    it('reports no more pages when a partial page came back', () =>
    {
        expect(hasMorePages(CHAT_PAGE_SIZE - 1)).toBe(false);
    });

    it('reports no more pages when zero results came back', () =>
    {
        expect(hasMorePages(0)).toBe(false);
    });

    it('reports no more pages for a count larger than the page size (defensive — should not occur in practice)', () =>
    {
        expect(hasMorePages(CHAT_PAGE_SIZE + 1)).toBe(false);
    });
});
