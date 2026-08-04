import type { PageId } from '@shared/pages/pageIds';

// Web's concrete route path for every canonical page. `as const satisfies`
// means TypeScript refuses to compile if a PageId is ever added to shared
// without a matching entry here.
export const PAGE_ROUTES =
{
    welcome:          '/welcome',
    login:            '/login',
    signup:           '/signup',
    menu:             '/menu',
    profile:          '/profile',
    additionalPhotos: '/profile/photos',
    discover:         '/discover',
    peerProfile:      '/peer/:peer_id',
    peerPhotos:       '/peer/:peer_id/photos',
    chatHistory:      '/chat',
    chat:             '/chat/:peer_id',
} as const satisfies Record<PageId, string>;
