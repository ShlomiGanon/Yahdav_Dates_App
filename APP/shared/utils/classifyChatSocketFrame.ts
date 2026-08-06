import type { Message } from '../types/chat';

export type ChatSocketFrame =
    | { kind: 'ack';     message_id: string }
    | { kind: 'ignore' }
    | { kind: 'message'; message: Message };

// Classifies a raw chat WebSocket text frame into what a caller needs to
// react to: a delivery ack for a message this client just sent (swap a
// temp id for the server-confirmed one), something to ignore (a parse
// failure, a non-object frame, a senderless frame, a server error frame,
// or a keepalive pong), or an incoming chat message. Was duplicated
// near-identically between mobile's hooks/useMessages.ts and web's
// ChatMasterDetail.tsx (both as a function named handleSocketFrame).
//
// Deliberately stops at classification. Any extra validation a specific
// caller wants on top of the baseline sender_id check (e.g. web also
// requires `content` to be defined before treating a frame as a real
// message) and all stateful reaction — ref bookkeeping, setState, marking
// a thread read, scrolling, reloading a conversation list — stay
// platform-specific, since none of that belongs in a framework-free
// shared module.
export function classifyChatSocketFrame(raw: string): ChatSocketFrame
{
    let frame: unknown;

    try
    {
        frame = JSON.parse(raw);
    }
    catch
    {
        return { kind: 'ignore' };
    }

    if (!frame || typeof frame !== 'object')
    {
        return { kind: 'ignore' };
    }

    const parsed = frame as Message & { type?: string };

    if (parsed.type === 'ack' && parsed.message_id)
    {
        return { kind: 'ack', message_id: parsed.message_id };
    }

    if (parsed.type === 'error' || parsed.type === 'pong')
    {
        return { kind: 'ignore' };
    }

    if (!parsed.sender_id)
    {
        return { kind: 'ignore' };
    }

    return { kind: 'message', message: parsed };
}
