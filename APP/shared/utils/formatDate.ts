import { formatDistanceToNow, isToday, isYesterday, format } from 'date-fns';
import { he } from 'date-fns/locale';

export function formatMessageTime(iso: string): string
{
    const date = new Date(iso);

    if (isNaN(date.getTime()))
    {
        return '';
    }

    return format(date, 'HH:mm');
}

export function formatConversationTime(iso: string | null): string
{
    if (!iso)
    {
        return '';
    }

    const date = new Date(iso);

    if (isNaN(date.getTime()))
    {
        return '';
    }

    const diffMs = Date.now() - date.getTime();

    if (diffMs < 60_000)
    {
        return 'עכשיו';
    }

    if (isToday(date))
    {
        return formatDistanceToNow(date, { locale: he, addSuffix: true });
    }

    if (isYesterday(date))
    {
        return 'אתמול';
    }

    return format(date, 'dd/MM');
}
