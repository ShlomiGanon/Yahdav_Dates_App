import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { format } from 'date-fns';
import { he } from 'date-fns/locale';
import { Avatar } from '../../components/Avatar';
import { StatusBadge } from '../../components/Badge';
import { Button } from '../../components/Button';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { StatusSelect } from '../../components/StatusSelect';
import type { UserStatus } from '../../types';
import { useUser } from './hooks/useUser';

function formatDate(iso: string | null | undefined) {
  if (!iso) return '—';
  try {
    return format(new Date(iso), 'dd/MM/yyyy HH:mm', { locale: he });
  } catch {
    return '—';
  }
}

const GENDER_MAP: Record<string, string> = {
  male:   'גבר',
  female: 'אישה',
  other:  'אחר',
};

export function UserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user, loading, error, saving, deleting, updateStatus, deleteUser } = useUser(id!);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [actionError, setActionError] = useState('');

  async function handleStatusChange(s: UserStatus) {
    setActionError('');
    const result = await updateStatus(s);
    if (!result.success) {
      setActionError(result.message);
    }
  }

  async function handleDelete() {
    const result = await deleteUser();
    setConfirmOpen(false);
    if (result.success) {
      navigate('/admin/users', { replace: true });
    } else {
      setActionError(result.message);
    }
  }

  if (loading) {
    return <div className="py-16 text-center text-gray-400">טוען...</div>;
  }

  if (error || !user) {
    return (
      <div className="py-16 text-center">
        <p className="text-red-500">{error || 'משתמש לא נמצא'}</p>
        <Button variant="ghost" size="sm" className="mt-4" onClick={() => navigate(-1)}>
          חזרה
        </Button>
      </div>
    );
  }

  return (
    <>
      <ConfirmDialog
        open={confirmOpen}
        title="מחיקת משתמש"
        message={`האם אתה בטוח שברצונך למחוק את ${user.name}? פעולה זו אינה הפיכה.`}
        confirmLabel="מחיקה"
        onConfirm={handleDelete}
        onCancel={() => setConfirmOpen(false)}
        loading={deleting}
      />

      <div className="mx-auto max-w-2xl space-y-6">
        {/* Back */}
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          ← חזרה לרשימה
        </button>

        {/* Header card */}
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <Avatar src={user.photo_url} name={user.name} size="lg" />
              <div>
                <h1 className="text-xl font-bold text-gray-900">{user.name || '—'}</h1>
                <p className="text-sm text-gray-500">@{user.username}</p>
                <div className="mt-1">
                  <StatusBadge status={user.status} />
                </div>
              </div>
            </div>

            <Button variant="danger" size="sm" onClick={() => setConfirmOpen(true)}>
              מחיקה
            </Button>
          </div>
          {actionError && (
            <p className="mt-3 text-sm text-red-500" role="alert">{actionError}</p>
          )}
        </div>

        {/* Status change */}
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-gray-800">שינוי סטטוס</h2>
          <div className="flex items-center gap-3">
            <StatusSelect value={user.status} onChange={handleStatusChange} disabled={saving} />
            {saving && <span className="text-sm text-gray-400">שומר...</span>}
            {actionError && <span className="text-sm text-red-500">{actionError}</span>}
          </div>
        </div>

        {/* Profile info */}
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-gray-800">פרופיל</h2>
          <dl className="space-y-3">
            <Row label="אימייל" value={user.email ?? '—'} />
            <Row label="מגדר" value={(GENDER_MAP[user.gender] ?? user.gender) || '—'} />
            <Row label="תאריך לידה" value={user.date_of_birth || '—'} />
            <Row label="עיר" value={user.city || '—'} />
            <Row label="אזור" value={user.region || '—'} />
            {user.bio && <Row label="ביוגרפיה" value={user.bio} />}
          </dl>
        </div>

        {/* Account info */}
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-gray-800">חשבון</h2>
          <dl className="space-y-3">
            <Row label="מזהה" value={user.user_id} mono />
            <Row label="תאריך הצטרפות" value={formatDate(user.registered_at)} />
            <Row label="כניסה אחרונה" value={formatDate(user.last_login_at)} />
            <Row label="עודכן" value={formatDate(user.updated_at)} />
            <Row label="מנהל" value={user.is_admin ? 'כן' : 'לא'} />
          </dl>
        </div>
      </div>
    </>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start gap-4">
      <dt className="w-32 flex-shrink-0 text-sm font-medium text-gray-500">{label}</dt>
      <dd className={`text-sm text-gray-800 ${mono ? 'font-mono text-xs' : ''}`}>{value}</dd>
    </div>
  );
}
