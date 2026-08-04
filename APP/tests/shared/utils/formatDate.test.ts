import { formatMessageTime, formatConversationTime } from '../../../shared/utils/formatDate';

describe('formatMessageTime', () =>
{
    it('formats a valid ISO timestamp as HH:mm', () =>
    {
        const iso = new Date(2024, 0, 15, 14, 5).toISOString();

        expect(formatMessageTime(iso)).toMatch(/^\d{2}:\d{2}$/);
    });

    it('pads single-digit hours and minutes', () =>
    {
        const iso = new Date(2024, 0, 15, 9, 3).toISOString();

        expect(formatMessageTime(iso)).toBe('09:03');
    });

    // Previously a known bug tracked via web's it.fails(): date-fns' format()
    // throws a RangeError on an invalid Date rather than returning a fallback
    // string. Fixed as part of consolidating mobile's separately-forked (and
    // already-guarded) implementation back into this shared version.
    it('returns an empty string for an invalid date string, instead of throwing', () =>
    {
        expect(formatMessageTime('not-a-date')).toBe('');
    });

    it('returns an empty string for an empty string, instead of throwing', () =>
    {
        expect(formatMessageTime('')).toBe('');
    });
});

describe('formatConversationTime', () =>
{
    it('returns an empty string for null', () =>
    {
        expect(formatConversationTime(null)).toBe('');
    });

    it('returns an empty string for an invalid date string, instead of throwing', () =>
    {
        expect(formatConversationTime('not-a-date')).toBe('');
    });

    it('returns "עכשיו" for a timestamp less than a minute old', () =>
    {
        const iso = new Date(Date.now() - 10_000).toISOString();

        expect(formatConversationTime(iso)).toBe('עכשיו');
    });

    it('returns a relative Hebrew string for a timestamp earlier today (but over a minute old)', () =>
    {
        const iso = new Date(Date.now() - 5 * 60_000).toISOString();
        const result = formatConversationTime(iso);

        expect(result).not.toBe('');
        expect(result).not.toBe('עכשיו');
        expect(result).not.toBe('אתמול');
    });

    it('returns "אתמול" for a timestamp from yesterday', () =>
    {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        yesterday.setHours(12, 0, 0, 0);

        expect(formatConversationTime(yesterday.toISOString())).toBe('אתמול');
    });

    it('returns a dd/MM date for anything older than yesterday', () =>
    {
        const older = new Date();
        older.setDate(older.getDate() - 10);

        expect(formatConversationTime(older.toISOString())).toMatch(/^\d{2}\/\d{2}$/);
    });
});
