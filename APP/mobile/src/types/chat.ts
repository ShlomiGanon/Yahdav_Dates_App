export type Message = {
  message_id: string;
  sender_id:  string;
  content:    string;
  msg_type:   'TEXT' | 'AUDIO' | 'IMAGE';
  created_at: string;
};

export type Conversation = {
  peer_id:         string;
  peer_name:       string;
  last_content:    string | null;
  last_msg_type:   'TEXT' | 'AUDIO' | 'IMAGE' | null;
  last_sender_id:  string | null;
  last_created_at: string | null;
  unread_count:    number;
};
