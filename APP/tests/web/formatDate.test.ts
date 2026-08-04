import { describe, it, expect } from 'vitest';
import { formatMessageTime, formatConversationTime } from '@shared/utils/formatDate';

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

    // Regression test for improve.md's finding that shared/utils/formatDate.ts
    // lacks the NaN guard mobile's local copy has (mobile/src/utils/formatDate.ts
    // checks `isNaN(d.getTime())` before formatting; shared's version doesn't).
    // date-fns' format() throws a RangeError on an invalid Date rather than
    // returning a fallback string, so this currently throws instead of
    // returning ''.
    it.fails('does not throw on an invalid date string — returns an empty string instead', () =>
    {
        expect(formatMessageTime('not-a-date')).toBe('');
    });

    it.fails('does not throw on an empty string', () =>
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

    it('returns "עכשיו" for a timestamp less than a minute old', () =>
    {
        const iso = new Date(Date.now() - 10_000).toISOString();

        expect(formatConversationTime(iso)).toBe('עכשיו');
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

    it.fails('does not throw on an invalid date string', () =>
    {
        expect(formatConversationTime('not-a-date')).toBe('');
    });
});
