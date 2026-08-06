import { classifyChatSocketFrame } from '../../../shared/utils/classifyChatSocketFrame';

// Pins the frame-classification logic that was duplicated near-identically
// between mobile's hooks/useMessages.ts and web's ChatMasterDetail.tsx
// (both as handleSocketFrame). See APP/review.md's mobile/web
// ack-reconciliation gap note for the history here.
describe('classifyChatSocketFrame', () =>
{
    it('classifies a well-formed ack frame', () =>
    {
        const raw = JSON.stringify({ type: 'ack', message_id: 'real-42' });
        expect(classifyChatSocketFrame(raw)).toEqual({ kind: 'ack', message_id: 'real-42' });
    });

    it('ignores an ack frame with no message_id', () =>
    {
        const raw = JSON.stringify({ type: 'ack' });
        expect(classifyChatSocketFrame(raw)).toEqual({ kind: 'ignore' });
    });

    it('ignores an error frame', () =>
    {
        const raw = JSON.stringify({ type: 'error', message: 'bad request' });
        expect(classifyChatSocketFrame(raw)).toEqual({ kind: 'ignore' });
    });

    it('ignores a pong frame', () =>
    {
        const raw = JSON.stringify({ type: 'pong' });
        expect(classifyChatSocketFrame(raw)).toEqual({ kind: 'ignore' });
    });

    it('ignores malformed JSON', () =>
    {
        expect(classifyChatSocketFrame('not json')).toEqual({ kind: 'ignore' });
    });

    it('ignores a JSON primitive (e.g. "null")', () =>
    {
        expect(classifyChatSocketFrame('null')).toEqual({ kind: 'ignore' });
        expect(classifyChatSocketFrame('42')).toEqual({ kind: 'ignore' });
        expect(classifyChatSocketFrame('"hello"')).toEqual({ kind: 'ignore' });
    });

    it('ignores a frame with no sender_id', () =>
    {
        const raw = JSON.stringify({ content: 'hi', msg_type: 'TEXT', created_at: '2026-01-01T00:00:00.000Z' });
        expect(classifyChatSocketFrame(raw)).toEqual({ kind: 'ignore' });
    });

    it('classifies a well-formed incoming message', () =>
    {
        const message = {
            message_id: 'm-1',
            sender_id:  'user-7',
            content:    'hello there',
            msg_type:   'TEXT' as const,
            created_at: '2026-01-01T00:00:00.000Z',
        };
        expect(classifyChatSocketFrame(JSON.stringify(message))).toEqual({ kind: 'message', message });
    });

    it('still classifies a message frame with content undefined — extra validation is a caller concern', () =>
    {
        const raw = JSON.stringify({ message_id: 'm-2', sender_id: 'user-7', msg_type: 'TEXT', created_at: '2026-01-01T00:00:00.000Z' });
        const result = classifyChatSocketFrame(raw);
        expect(result.kind).toBe('message');
    });
});
