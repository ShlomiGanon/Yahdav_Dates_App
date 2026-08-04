export type MsgType = 'TEXT' | 'AUDIO' | 'IMAGE';

export interface Message
{
    message_id: string;
    sender_id:  string;
    content:    string;
    msg_type:   MsgType;
    created_at: string;
}

export interface Conversation
{
    peer_id:         string;
    peer_name:       string;
    last_content:    string | null;
    last_msg_type:   MsgType | null;
    last_sender_id:  string | null;
    last_created_at: string | null;
    unread_count:    number;
}
