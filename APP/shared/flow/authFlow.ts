export type AuthDestination = 'home' | 'login';

// Event rules: fired once, right after a specific action succeeds. A
// platform looks up the destination here and performs one explicit
// navigation call.
export type AuthFlowEvent =
    | 'afterLogin'
    | 'afterSignup'
    | 'afterLogout'
    | 'afterSessionExpired';

export const AUTH_FLOW_EVENTS =
{
    afterLogin:          'home',
    afterSignup:         'login',
    afterLogout:         'login',
    afterSessionExpired: 'login',
} as const satisfies Record<AuthFlowEvent, AuthDestination>;

// Guard rules: standing invariants a platform enforces continuously
// (a route guard component on web, which stack is mounted on mobile) —
// not a one-off call.
export type AuthFlowGuard =
    | 'whenAuthenticatedOnAuthScreen'
    | 'whenUnauthenticatedOnProtectedScreen';

export const AUTH_FLOW_GUARDS =
{
    whenAuthenticatedOnAuthScreen:        'home',
    whenUnauthenticatedOnProtectedScreen: 'login',
} as const satisfies Record<AuthFlowGuard, AuthDestination>;
