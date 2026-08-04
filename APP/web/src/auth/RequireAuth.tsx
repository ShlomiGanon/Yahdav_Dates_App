import { Navigate, Outlet } from 'react-router-dom';
import { AUTH_FLOW_GUARDS } from '@shared/flow/authFlow';
import { useAuth } from './AuthContext';
import { WEB_DESTINATIONS } from './destinations';

export function RequireAuth()
{
    const { user, loading } = useAuth();

    if (loading)
    {
        return <div className="min-h-screen bg-background" />;
    }

    if (!user)
    {
        return <Navigate to={WEB_DESTINATIONS[AUTH_FLOW_GUARDS.whenUnauthenticatedOnProtectedScreen]} replace />;
    }

    return <Outlet />;
}
