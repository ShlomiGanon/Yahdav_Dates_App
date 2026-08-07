// The product's display name — was hand-copied as a raw string literal in
// web (index.html, AppShell.tsx, LoginPage.tsx, WelcomePage.tsx) and admin
// (index.html, LoginPage.tsx, Sidebar.tsx). Admin's own "ניהול" suffix
// stays local to admin — only the app name itself lives here.
export const APP_NAME = 'יחדיו';

// The default backend URL, used whenever a platform doesn't set its own
// override (VITE_API_BASE_URL on web, EXPO_PUBLIC_API_BASE_URL on mobile).
// Before this existed, both axios clients hand-copied the same
// 'http://localhost:3000' literal as their fallback — exactly the kind of
// drift-prone duplication this codebase's architecture explicitly guards
// against elsewhere. This is now the one place that literal lives.
//
// Each platform still needs its own env var, not just this constant,
// because they have genuinely different runtime needs: Expo Go on a
// physical device can't reach "localhost" (that resolves to the phone
// itself), so mobile dev/preview/production builds point at a real host
// via EXPO_PUBLIC_API_BASE_URL (see mobile/eas.json) — web has no
// equivalent constraint.
export const DEFAULT_API_BASE_URL = 'http://localhost:3000';

// How many additional (non-main) photos a profile may have. Was a named
// const on web (AdditionalPhotosPage.tsx) but a bare literal `4`, used
// twice, on mobile (AdditionalPhotosScreen.tsx) — the exact drift-prone
// pattern this file exists to prevent. See APP/review.md finding 2.8.
export const MAX_ADDITIONAL_PHOTOS = 4;
