import type { Conversation } from '../types/chat';

const PREVIEW_MAX = 38;

// The conversation-list preview text shown on both platforms — was two
// independent copies (mobile's ChatHistoryScreen.tsx, web's
// ChatMasterDetail.tsx) carrying the exact same truncation length, emoji
// strings, and self-sender prefix. See APP/review.md finding 2.3.
export function formatConversationPreview(conv: Conversation, selfId: string): string
{
    let body: string;

    if (conv.last_msg_type === 'AUDIO')
    {
        body = '🎤 הודעה קולית';
    }
    else if (conv.last_msg_type === 'IMAGE')
    {
        body = '📷 תמונה';
    }
    else
    {
        body = (conv.last_content || '').trim();

        if (body.length > PREVIEW_MAX)
        {
            body = body.slice(0, PREVIEW_MAX) + '…';
        }
    }

    const prefix = conv.last_sender_id === selfId ? 'את/ה: ' : '';
    return prefix + body;
}
