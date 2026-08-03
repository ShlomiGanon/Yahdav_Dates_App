import { v4 as uuidv4 } from 'uuid';
import { messagingQueries, MessageRow, ConversationRow } from '../database/queries/messaging.queries';

export interface Message {
  message_id: string;
  sender_id:  string;
  content:    string;
  msg_type:   string;
  created_at: string;
}

export interface Conversation {
  peer_id:         string;
  peer_name:       string;
  last_content:    string | null;
  last_msg_type:   string | null;
  last_sender_id:  string | null;
  last_created_at: string | null;
  unread_count:    number;
}

function toMessage(row: MessageRow): Message {
  return {
    message_id: row.message_id,
    sender_id:  row.sender_id,
    content:    row.content,
    msg_type:   row.msg_type,
    created_at: row.created_at,
  };
}

function toConversation(row: ConversationRow): Conversation {
  return {
    peer_id:         row.peer_id,
    peer_name:       row.peer_name,
    last_content:    row.last_content    ?? null,
    last_msg_type:   row.last_msg_type   ?? null,
    last_sender_id:  row.last_sender_id  ?? null,
    last_created_at: row.last_created_at ?? null,
    unread_count:    row.unread_count,
  };
}

export const MessageModel = {
  getConversations(userId: string): Conversation[] {
    return messagingQueries.getConversations(userId).map(toConversation);
  },

  getMessages(userId: string, peerId: string, limit: number, before?: string): Message[] {
    return messagingQueries.getMessages(userId, peerId, limit, before).map(toMessage);
  },

  send(senderId: string, recipientId: string, content: string, msgType: string): Message {
    const now = new Date().toISOString();
    const msg = {
      message_id:   uuidv4(),
      sender_id:    senderId,
      recipient_id: recipientId,
      content,
      msg_type:     msgType,
      created_at:   now,
    };
    messagingQueries.insert(msg);
    return toMessage({ ...msg, read_at: null });
  },

  markRead(userId: string, peerId: string): void {
    messagingQueries.markRead(userId, peerId, new Date().toISOString());
  },

  isBlocked(senderId: string, recipientId: string): boolean {
    return messagingQueries.isBlocked(senderId, recipientId);
  },
};
