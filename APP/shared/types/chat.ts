export interface Message
{
    message_id: string;
    sender_id:  string;
    content:    string;
    msg_type:   'TEXT' | 'IMAGE';
    created_at: string;
    is_read:    number;
}

export interface Conversation
{
    peer_id:         string;
    peer_name:       string;
    peer_photo:      string | null;
    last_content:    string | null;
    last_message_at: string | null;
    unread_count:    number;
}
