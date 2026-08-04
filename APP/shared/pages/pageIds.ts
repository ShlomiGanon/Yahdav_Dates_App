// The canonical set of pages in the end-user clients (web + mobile). The
// admin panel is a separate system and out of scope for this registry.
//
// Both clients must implement every one of these — even where full
// functionality isn't built yet, a page with this identifier must exist
// (see each platform's own next_missions.md for what's still a stub).
// Each platform maps every PageId to its own concrete route path or
// screen name (see web/src/pages/routes.ts, mobile/src/navigation/screenNames.ts)
// — this registry only defines the shared vocabulary, never a concrete
// path/screen shape, matching how @shared/flow/authFlow.ts's
// AuthDestination already works.
export type PageId =
    | 'welcome'
    | 'login'
    | 'signup'
    | 'menu'
    | 'profile'
    | 'additionalPhotos'
    | 'discover'
    | 'peerProfile'
    | 'peerPhotos'
    | 'chatHistory'
    | 'chat';

export const PAGE_IDS: readonly PageId[] =
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
