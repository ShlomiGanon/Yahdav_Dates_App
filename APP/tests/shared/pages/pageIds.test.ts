import { PAGE_IDS, PageId } from '../../../shared/pages/pageIds';

describe('PAGE_IDS', () =>
{
    it('has no duplicate entries', () =>
    {
        expect(new Set(PAGE_IDS).size).toBe(PAGE_IDS.length);
    });

    it('matches the exact expected page inventory', () =>
    {
        const expected: PageId[] =
        [
            'welcome',
            'login',
            'signup',
            'menu',
            'profile',
            'additionalPhotos',
            'discover',
            'peerProfile',
            'peerPhotos',
            'chatHistory',
            'chat',
        ];

        expect([...PAGE_IDS].sort()).toEqual([...expected].sort());
    });
});
