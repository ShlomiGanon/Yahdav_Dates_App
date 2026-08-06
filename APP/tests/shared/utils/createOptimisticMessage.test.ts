import { createOptimisticMessage } from '../../../shared/utils/createOptimisticMessage';

// Pins the optimistic-message shape that was previously duplicated in
// mobile's hooks/useMessages.ts (sendMessage) and web's
// ChatMasterDetail.tsx (handleSend). Was verified against a local
// reference implementation before this file existed (see APP/review.md
// finding 2.11 for that pinning pass); these are the same assertions, now
// run against the real export.
describe('createOptimisticMessage', () =>
{
    beforeEach(() =>
    {
        jest.useFakeTimers().setSystemTime(new Date('2026-01-15T10:30:00.000Z'));
    });

    afterEach(() =>
    {
        jest.useRealTimers();
    });

    it('builds a tmp-prefixed id from the current timestamp', () =>
    {
        const msg = createOptimisticMessage('hello', 'user-1');
        expect(msg.message_id).toBe(`tmp-${Date.now()}`);
    });

    it('carries the given content and sender id through unchanged', () =>
    {
        const msg = createOptimisticMessage('hello there', 'user-42');
        expect(msg.content).toBe('hello there');
        expect(msg.sender_id).toBe('user-42');
    });

    it('always tags the message as TEXT', () =>
    {
        const msg = createOptimisticMessage('hello', 'user-1');
        expect(msg.msg_type).toBe('TEXT');
    });

    it('stamps created_at as the current time in ISO format', () =>
    {
        const msg = createOptimisticMessage('hello', 'user-1');
        expect(msg.created_at).toBe('2026-01-15T10:30:00.000Z');
    });

    it('produces distinct ids for messages sent at different times', () =>
    {
        const first = createOptimisticMessage('a', 'user-1');
        jest.setSystemTime(new Date('2026-01-15T10:30:00.500Z'));
        const second = createOptimisticMessage('b', 'user-1');
        expect(first.message_id).not.toBe(second.message_id);
    });
});
