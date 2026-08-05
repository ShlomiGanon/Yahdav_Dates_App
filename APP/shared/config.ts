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
