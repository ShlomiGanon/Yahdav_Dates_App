import type { AuthDestination } from '@shared/flow/authFlow';

export const MOBILE_DESTINATIONS =
{
    home:  'Menu',
    login: 'Login',
} as const satisfies Record<AuthDestination, 'Menu' | 'Login'>;
