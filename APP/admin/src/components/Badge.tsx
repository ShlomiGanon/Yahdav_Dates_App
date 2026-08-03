import type { UserStatus } from '../types';

const STATUS_MAP: Record<UserStatus, { label: string; cls: string }> = {
  active:    { label: 'פעיל',   cls: 'bg-green-100 text-green-700' },
  suspended: { label: 'מושהה', cls: 'bg-yellow-100 text-yellow-700' },
  banned:    { label: 'חסום',  cls: 'bg-red-100 text-red-700' },
};

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS_MAP[status as UserStatus] ?? { label: status, cls: 'bg-gray-100 text-gray-600' };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${s.cls}`}>
      {s.label}
    </span>
  );
}
