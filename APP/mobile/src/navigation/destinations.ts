import type { AuthDestination } from '@shared/flow/authFlow';
import { SCREEN_NAMES } from './screenNames';

// "home" (the post-login/signup, already-authenticated destination) is the
// Menu screen. Derived from SCREEN_NAMES rather than a fresh literal, so this
// can never drift from wherever Menu's own screen name is registered.
export const MOBILE_DESTINATIONS =
{
    home:  SCREEN_NAMES.menu,
    login: SCREEN_NAMES.login,
} as const satisfies Record<AuthDestination, 'Menu' | 'Login'>;
