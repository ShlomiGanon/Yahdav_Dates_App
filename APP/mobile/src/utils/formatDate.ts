import { format, isToday, isYesterday, formatDistanceToNow } from 'date-fns';
import { he } from 'date-fns/locale';

/** Chat bubble timestamp — always HH:mm */
export function formatMessageTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return format(d, 'HH:mm');
}

/** Conversation list timestamp — relative today, "אתמול", or dd/MM */
export function formatConversationTime(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const diffMs = Date.now() - d.getTime();
  if (diffMs < 60_000) return 'עכשיו';
  if (isToday(d)) return formatDistanceToNow(d, { locale: he, addSuffix: true });
  if (isYesterday(d)) return 'אתמול';
  return format(d, 'dd/MM');
}
