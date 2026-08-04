import { formatDistanceToNow, isToday, isYesterday, format } from 'date-fns';
import { he } from 'date-fns/locale';

export function formatMessageTime(iso: string): string
{
    return format(new Date(iso), 'HH:mm');
}

export function formatConversationTime(iso: string | null): string
{
    if (!iso)
    {
        return '';
    }

    const date   = new Date(iso);
    const diffMs = Date.now() - date.getTime();

    if (isToday(date))
    {
        if (diffMs < 60_000)
        {
            return 'עכשיו';
        }

        return formatDistanceToNow(date, { locale: he, addSuffix: true });
    }

    if (isYesterday(date))
    {
        return 'אתמול';
    }

    return format(date, 'dd/MM', { locale: he });
}
