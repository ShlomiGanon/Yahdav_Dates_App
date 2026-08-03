import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';

export function Topbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate('/login', { replace: true });
  }

  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4">
      <span className="text-sm text-gray-500">מחובר כ: {user?.username}</span>
      <Button variant="ghost" size="sm" onClick={handleLogout}>
        יציאה
      </Button>
    </header>
  );
}
