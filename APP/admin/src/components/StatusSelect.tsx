import type { UserStatus } from '../types';

const OPTIONS: { value: UserStatus; label: string }[] = [
  { value: 'active',    label: 'פעיל' },
  { value: 'suspended', label: 'מושהה' },
  { value: 'banned',    label: 'חסום' },
];

interface StatusSelectProps {
  value: UserStatus;
  onChange: (s: UserStatus) => void;
  disabled?: boolean;
}

export function StatusSelect({ value, onChange, disabled }: StatusSelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as UserStatus)}
      disabled={disabled}
      className="rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:opacity-60"
    >
      {OPTIONS.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
