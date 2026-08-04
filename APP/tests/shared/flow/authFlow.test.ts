import
{
    AUTH_FLOW_EVENTS,
    AUTH_FLOW_GUARDS,
    AuthDestination,
} from '../../../shared/flow/authFlow';

const VALID_DESTINATIONS: AuthDestination[] = ['home', 'login'];

describe('AUTH_FLOW_EVENTS', () =>
{
    it('has exactly the four expected event keys', () =>
    {
        expect(Object.keys(AUTH_FLOW_EVENTS).sort()).toEqual(
        [
            'afterLogin',
            'afterLogout',
            'afterSessionExpired',
            'afterSignup',
        ]);
    });

    it('maps every event to a valid AuthDestination', () =>
    {
        for (const destination of Object.values(AUTH_FLOW_EVENTS))
        {
            expect(VALID_DESTINATIONS).toContain(destination);
        }
    });

    it('sends a successful login to home', () =>
    {
        expect(AUTH_FLOW_EVENTS.afterLogin).toBe('home');
    });

    it('sends signup, logout, and session expiry to login', () =>
    {
        expect(AUTH_FLOW_EVENTS.afterSignup).toBe('login');
        expect(AUTH_FLOW_EVENTS.afterLogout).toBe('login');
        expect(AUTH_FLOW_EVENTS.afterSessionExpired).toBe('login');
    });
});

describe('AUTH_FLOW_GUARDS', () =>
{
    it('has exactly the two expected guard keys', () =>
    {
        expect(Object.keys(AUTH_FLOW_GUARDS).sort()).toEqual(
        [
            'whenAuthenticatedOnAuthScreen',
            'whenUnauthenticatedOnProtectedScreen',
        ]);
    });

    it('maps every guard to a valid AuthDestination', () =>
    {
        for (const destination of Object.values(AUTH_FLOW_GUARDS))
        {
            expect(VALID_DESTINATIONS).toContain(destination);
        }
    });

    it('sends an authenticated user away from the auth screen, to home', () =>
    {
        expect(AUTH_FLOW_GUARDS.whenAuthenticatedOnAuthScreen).toBe('home');
    });

    it('sends an unauthenticated user away from a protected screen, to login', () =>
    {
        expect(AUTH_FLOW_GUARDS.whenUnauthenticatedOnProtectedScreen).toBe('login');
    });
});
