import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from './AuthContext';

export function RequireAuth() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-400 text-lg">
        טוען...
      </div>
    );
  }

  // Checks is_admin here too, not just that a session exists — login()
  // already refuses a non-admin at sign-in time, but a session restored
  // via /api/auth/refresh doesn't re-run that gate. is_admin comes back
  // fresh from the DB on every login/refresh/me call (see
  // backend/src/routes/auth.routes.ts), so this stays correct even for an
  // admin who was demoted after their token was issued.
  return user?.is_admin ? <Outlet /> : <Navigate to="/admin/login" replace />;
}
