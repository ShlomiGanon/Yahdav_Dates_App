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

  return user ? <Navigate to="/admin/users" replace /> : <Outlet />;
}
