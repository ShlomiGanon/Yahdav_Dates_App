import type { AuthDestination } from '@shared/flow/authFlow';

export const WEB_DESTINATIONS: Record<AuthDestination, string> =
{
    home:  '/discover',
    login: '/login',
};
