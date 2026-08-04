import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from './AuthContext';

export function RedirectIfAuthed()
{
    const { user, loading } = useAuth();

    if (loading)
    {
        return <div className="min-h-screen bg-background" />;
    }

    if (user)
    {
        return <Navigate to="/discover" replace />;
    }

    return <Outlet />;
}
