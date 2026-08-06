# Web — Page Buildout (Complete)

This file originally tracked 8 web pages that existed only as routed
`PageShell` stubs. All 8 are now fully built, at feature parity with
their mobile equivalents (see `architecture.md` for the handful of
deliberate, documented UX differences between the two clients). Kept
here as a historical record rather than deleted outright.

## What was built

- **Welcome** (`/welcome`, `WelcomePage.tsx`) — landing content for
  unauthenticated visitors (hero image, login/signup entry points).
- **Menu** (`/menu`, `MenuPage.tsx`) — dashboard of quick-link cards to
  Discover, Chat, and Profile. Deliberately *not* a copy of mobile's
  3-button hub: web's `AppShell` sidebar already handles navigation, so
  Menu is a landing pane instead, per the documented UX divergence.
- **AdditionalPhotos** (`/profile/photos`, `AdditionalPhotosPage.tsx`) —
  photo grid, upload, delete-with-confirmation, `MAX_ADDITIONAL_PHOTOS`
  limit handling (shared constant with mobile).
- **PeerPhotos** (`/peer/:peer_id/photos`, `PeerPhotosPage.tsx`) —
  full-bleed, distraction-free photo viewer with prev/next paging,
  outside `AppShell` by design (same as mobile's full-bleed viewer).
- **Discover** (`/discover`, `DiscoverPage.tsx`) — candidate grid,
  pagination ("load more"), and a slide-in detail panel — web's
  equivalent of mobile's bottom sheet.
- **PeerProfile** (`/peer/:peer_id`, `PeerProfilePage.tsx`) — full peer
  profile view, block-user flow with confirmation.
- **ChatHistory** (`/chat`, `ChatHistoryPage.tsx`) and **Chat**
  (`/chat/:peer_id`, `ChatPage.tsx`) — both render the shared
  `ChatMasterDetail.tsx` component: a single master-detail view merging
  what mobile splits into two screens (`ChatHistoryScreen` +
  `ChatScreen`), since a wide viewport has room for both at once. One
  WebSocket per mount feeds both the conversation list and the open
  thread — live send/receive, optimistic sends with ack-reconciliation,
  older-message pagination with scroll-anchoring.

## Notes

- All 8 pages import shared logic from `@shared/*` (validation,
  formatters, pagination constants, `clientMessage` copy, domain
  utilities like `calcAge`/`genderLabel`/`blockPeer`) rather than
  reimplementing it locally — see `APP/review.md` for the audit that
  drove that consolidation.
- Known, deliberate gap versus mobile: web does not client-side resize
  photos before upload (mobile downsizes to 1080px/0.8 JPEG quality via
  `expo-image-manipulator`). This is an open product decision, not a
  bug — tracked in `APP/project.md`'s "What Is Left To Do".
