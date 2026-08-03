import { getDb } from '../connection';

export interface MessageRow {
  message_id: string;
  sender_id: string;
  recipient_id: string;
  content: string;
  msg_type: string;
  created_at: string;
  read_at: string | null;
}

export interface ConversationRow {
  peer_id: string;
  peer_name: string;
  last_content: string;
  last_msg_type: string;
  last_sender_id: string;
  last_created_at: string;
  unread_count: number;
}

export const messagingQueries = {
  // Returns conversations as seen by userId: each unique peer, latest message, unread count
  getConversations(userId: string): ConversationRow[] {
    return getDb()
      .prepare(`
        WITH ranked AS (
          SELECT
            CASE WHEN sender_id = ? THEN recipient_id ELSE sender_id END AS peer_id,
            content        AS last_content,
            msg_type       AS last_msg_type,
            sender_id      AS last_sender_id,
            created_at     AS last_created_at,
            ROW_NUMBER() OVER (
              PARTITION BY CASE WHEN sender_id = ? THEN recipient_id ELSE sender_id END
              ORDER BY created_at DESC
            ) AS rn
          FROM direct_messages
          WHERE sender_id = ? OR recipient_id = ?
        )
        SELECT r.peer_id,
               p.name       AS peer_name,
               r.last_content,
               r.last_msg_type,
               r.last_sender_id,
               r.last_created_at,
               (
                 SELECT COUNT(*)
                 FROM direct_messages m2
                 WHERE m2.sender_id = r.peer_id
                   AND m2.recipient_id = ?
                   AND m2.read_at IS NULL
               ) AS unread_count
        FROM ranked r
        JOIN user_profiles p ON p.user_id = r.peer_id
        WHERE r.rn = 1
        ORDER BY r.last_created_at DESC
      `)
      .all(userId, userId, userId, userId, userId) as unknown as ConversationRow[];
  },

  // Paginate: newest first (DESC). `before` is a message_id; cursor is that message's created_at.
  getMessages(userId: string, peerId: string, limit: number, before?: string): MessageRow[] {
    const db = getDb();
    if (before) {
      return db
        .prepare(`
          SELECT * FROM direct_messages
          WHERE ((sender_id = ? AND recipient_id = ?) OR (sender_id = ? AND recipient_id = ?))
            AND created_at < (SELECT created_at FROM direct_messages WHERE message_id = ?)
          ORDER BY created_at DESC
          LIMIT ?
        `)
        .all(userId, peerId, peerId, userId, before, limit) as unknown as MessageRow[];
    }
    return db
      .prepare(`
        SELECT * FROM direct_messages
        WHERE (sender_id = ? AND recipient_id = ?) OR (sender_id = ? AND recipient_id = ?)
        ORDER BY created_at DESC
        LIMIT ?
      `)
      .all(userId, peerId, peerId, userId, limit) as unknown as MessageRow[];
  },

  insert(msg: {
    message_id: string;
    sender_id: string;
    recipient_id: string;
    content: string;
    msg_type: string;
    created_at: string;
  }): void {
    getDb()
      .prepare(`
        INSERT INTO direct_messages (message_id, sender_id, recipient_id, content, msg_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
      `)
      .run(msg.message_id, msg.sender_id, msg.recipient_id, msg.content, msg.msg_type, msg.created_at);
  },

  markRead(userId: string, peerId: string, readAt: string): void {
    getDb()
      .prepare(`
        UPDATE direct_messages
        SET read_at = ?
        WHERE sender_id = ? AND recipient_id = ? AND read_at IS NULL
      `)
      .run(readAt, peerId, userId);
  },

  // Check that neither user has blocked the other before allowing a message
  isBlocked(senderId: string, recipientId: string): boolean {
    const row = getDb()
      .prepare(`
        SELECT 1 FROM user_blocks
        WHERE (blocker_id = ? AND blocked_id = ?)
           OR (blocker_id = ? AND blocked_id = ?)
        LIMIT 1
      `)
      .get(senderId, recipientId, recipientId, senderId) as { 1: number } | undefined;
    return row !== undefined;
  },
};
