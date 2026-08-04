import type { AuthDestination } from '@shared/flow/authFlow';
import { PAGE_ROUTES } from '../pages/routes';

// "home" (the post-login/signup, already-authenticated destination) is the
// Menu page, not Discover — Menu is the app's actual hub. Derived from
// PAGE_ROUTES rather than a fresh literal, so this can never drift from
// wherever Menu's own route is registered.
export const WEB_DESTINATIONS: Record<AuthDestination, string> =
{
    home:  PAGE_ROUTES.menu,
    login: PAGE_ROUTES.login,
};
