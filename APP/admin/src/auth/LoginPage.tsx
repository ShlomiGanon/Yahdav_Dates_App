import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';

export function LoginPage() {
  const { login } = useAuth();
  const navigate   = useNavigate();

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword]     = useState('');
  const [error, setError]           = useState('');
  const [loading, setLoading]       = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    if (!identifier.trim() || !password) {
      setError('יש למלא את כל השדות.');
      return;
    }

    setLoading(true);
    try {
      const result = await login(identifier.trim(), password);
      if (!result.success) {
        setError(result.message);
        return;
      }
      navigate('/admin/users', { replace: true });
    } catch {
      setError('שגיאת רשת, נסה שוב.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-md">
        <h1 className="mb-6 text-center text-2xl font-bold text-gray-800">יחדיו — ניהול</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="admin-login-identifier" className="mb-1 block text-sm font-medium text-gray-700">
              שם משתמש / אימייל
            </label>
            <input
              id="admin-login-identifier"
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              autoFocus
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label htmlFor="admin-login-password" className="mb-1 block text-sm font-medium text-gray-700">סיסמה</label>
            <input
              id="admin-login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600" role="alert">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'מתחבר...' : 'כניסה'}
          </button>
        </form>
      </div>
    </div>
  );
}
