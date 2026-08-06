import type { Message } from '../types/chat';

// Builds the locally-displayed message shown immediately on send, before
// the server confirms it — was duplicated identically in mobile's
// hooks/useMessages.ts (sendMessage) and web's ChatMasterDetail.tsx
// (handleSend). Reconciling this temp id with the server-confirmed one
// (on send-response or websocket ack) stays platform-specific — mobile and
// web currently do this differently, and mobile doesn't reconcile
// socket-sent messages at all (see APP/review.md finding 2.11's side
// observation) — so only the construction itself is shared here.
export function createOptimisticMessage(content: string, senderId: string): Message
{
    return {
        message_id: `tmp-${Date.now()}`,
        sender_id:  senderId,
        content,
        msg_type:   'TEXT',
        created_at: new Date().toISOString(),
    };
}
