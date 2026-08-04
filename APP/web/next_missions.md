# Web — Next Missions

Pages that exist as routed stubs (per the shared `PageId` contract in
`APP/shared/pages/pageIds.ts`) but do not yet have real functionality on
web. Each renders only a `PageShell` with a placeholder sentence. Building
these out to full feature parity (matching the equivalent mobile screen,
where one already exists) is deferred future work, tracked here.

## Newly-created stubs (this task)

- **Welcome** (`/welcome`, `WelcomePage.tsx`) — needs real landing/marketing
  content for unauthenticated visitors. Mobile equivalent:
  `mobile/src/screens/welcome/WelcomeScreen.tsx` (fully built).
- **Menu** (`/menu`, `MenuPage.tsx`) — needs the actual navigation hub UI
  (links to Profile, Discover, Chat, etc.). Mobile equivalent:
  `mobile/src/screens/menu/MenuScreen.tsx`.
- **AdditionalPhotos** (`/profile/photos`, `AdditionalPhotosPage.tsx`) —
  needs photo grid + upload. Mobile equivalent:
  `mobile/src/screens/profile/AdditionalPhotosScreen.tsx` (fully built,
  real feature).
- **PeerPhotos** (`/peer/:peer_id/photos`, `PeerPhotosPage.tsx`) — needs
  paged photo viewer for another user's photos. Mobile equivalent:
  `mobile/src/screens/peer/PeerPhotosScreen.tsx` (fully built, real
  feature).

## Pre-existing stubs

- **Discover** (`/discover`, `DiscoverPage.tsx`) — needs candidate browsing
  UI. Mobile equivalent: `mobile/src/screens/discover/DiscoverScreen.tsx`
  (fully built, real feature — candidate browsing + bottom sheet).
- **PeerProfile** (`/peer/:peer_id`, `PeerProfilePage.tsx`) — needs another
  user's profile view.
- **ChatHistory** (`/chat`, `ChatHistoryPage.tsx`) — needs the list of
  conversations.
- **Chat** (`/chat/:peer_id`, `ChatPage.tsx`) — needs the actual messaging
  UI.

## Notes

- All 8 pages are already wired into routing (`App.tsx` / `pages/routes.ts`)
  and reachable at their final URLs — only the content inside each is a
  placeholder.
- When implementing any of these, follow the existing `PageShell` wrapper
  convention unless the feature's needs outgrow it.
