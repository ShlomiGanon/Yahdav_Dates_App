import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { he } from 'date-fns/locale';
import { Avatar } from '../../components/Avatar';
import { StatusBadge } from '../../components/Badge';
import { Pagination } from '../../components/Pagination';
import { SearchInput } from '../../components/SearchInput';
import { useUsers } from './hooks/useUsers';

function formatDate(iso: string) {
  try {
    return format(new Date(iso), 'dd/MM/yyyy', { locale: he });
  } catch {
    return '—';
  }
}

export function UserListPage() {
  const navigate = useNavigate();
  const { users, total, page, totalPages, search, loading, error, setSearch, setPage } = useUsers();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">משתמשים</h1>
        <span className="text-sm text-gray-500">{total} סה"כ</span>
      </div>

      <div className="w-72">
        <SearchInput value={search} onChange={setSearch} placeholder="חיפוש לפי שם או עיר..." />
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600">{error}</div>
      )}

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50 text-right text-xs font-semibold uppercase tracking-wide text-gray-500">
              <th className="px-4 py-3">משתמש</th>
              <th className="px-4 py-3">שם משתמש</th>
              <th className="px-4 py-3">אימייל</th>
              <th className="px-4 py-3">סטטוס</th>
              <th className="px-4 py-3">תאריך הצטרפות</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="py-12 text-center text-gray-400">
                  טוען...
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-12 text-center text-gray-400">
                  לא נמצאו משתמשים
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr
                  key={u.user_id}
                  onClick={() => navigate(`/admin/users/${u.user_id}`)}
                  className="cursor-pointer border-b border-gray-50 transition-colors hover:bg-gray-50 last:border-0"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar src={u.photo_url} name={u.name} size="sm" />
                      <span className="font-medium text-gray-900">{u.name || '—'}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{u.username ?? '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{u.email ?? '—'}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={u.status} />
                  </td>
                  <td className="px-4 py-3 text-gray-500">{formatDate(u.registered_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Pagination page={page} totalPages={totalPages} onPage={setPage} />
    </div>
  );
}
