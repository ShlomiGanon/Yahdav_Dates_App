import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from './AuthContext';

export function RedirectIfAuthed() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-400 text-lg">
        טוען...
      </div>
    );
  }

  // Same is_admin check as RequireAuth — without it, a demoted admin whose
  // session still restores via /api/auth/refresh (user truthy, is_admin
  // false) would bounce forever: redirected away from /admin/login here,
  // then straight back to it by RequireAuth.
  return user?.is_admin ? <Navigate to="/admin/users" replace /> : <Outlet />;
}
