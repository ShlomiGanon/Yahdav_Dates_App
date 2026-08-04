import type { PageId } from '@shared/pages/pageIds';

// Mobile's concrete screen name for every canonical page. `as const satisfies`
// means TypeScript refuses to compile if a PageId is ever added to shared
// without a matching entry here — and the `as const` keeps each value's
// literal type intact, which React Navigation's `Stack.Screen name` prop
// requires (mirrors web/src/pages/routes.ts's PAGE_ROUTES).
export const SCREEN_NAMES =
{
    welcome:          'Welcome',
    login:            'Login',
    signup:           'Signup',
    menu:             'Menu',
    profile:          'Profile',
    additionalPhotos: 'AdditionalPhotos',
    discover:         'Discover',
    peerProfile:      'PeerProfile',
    peerPhotos:       'PeerPhotos',
    chatHistory:      'ChatHistory',
    chat:             'Chat',
} as const satisfies Record<PageId, string>;
