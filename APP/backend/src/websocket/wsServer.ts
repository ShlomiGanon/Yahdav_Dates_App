import { IncomingMessage } from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import { Server } from 'http';
import { SessionModel } from '../models/SessionModel';
import { MessageModel } from '../models/MessageModel';
import { profileQueries } from '../database/queries/profile.queries';
import { authQueries } from '../database/queries/auth.queries';
import { wsManager } from './wsManager';
import { sendPushNotification } from '../services/pushService';

interface IncomingFrame {
  type?:     string;
  peer_id?:  string;
  content?:  string;
  msg_type?: string;
}

const VALID_MSG_TYPES = new Set(['TEXT', 'AUDIO', 'IMAGE']);
const MAX_CONTENT_LENGTH = 4000;

function sendError(ws: WebSocket, code: string, detail: string): void {
  ws.send(JSON.stringify({ type: 'error', code, detail }));
}

export function attachWsServer(server: Server): void {
  const wss = new WebSocketServer({ server, path: '/ws' });

  wss.on('connection', (ws: WebSocket, req: IncomingMessage) => {
    // ── Authenticate ──────────────────────────────────────────────────────────
    const url    = new URL(req.url ?? '', 'http://localhost');
    const token  = url.searchParams.get('token') ?? '';
    let   userId = '';

    try {
      const payload = SessionModel.verifyAccess(token);
      userId = payload.sub;
    } catch {
      ws.close(4001, 'unauthorized');
      return;
    }

    wsManager.register(userId, ws);

    // ── Message handler ───────────────────────────────────────────────────────
    ws.on('message', (raw) => {
      let frame: IncomingFrame;
      try {
        frame = JSON.parse(raw.toString()) as IncomingFrame;
      } catch {
        return;
      }

      if (frame.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong' }));
        return;
      }

      // Treat any frame with peer_id + content as a message
      const { peer_id, content, msg_type = 'TEXT' } = frame;
      if (!peer_id || !content?.trim()) return;

      const trimmedContent = content.trim();

      if (trimmedContent.length > MAX_CONTENT_LENGTH) {
        sendError(ws, 'validation_error', 'ההודעה ארוכה מדי (מקסימום 4000 תווים)');
        return;
      }
      if (!VALID_MSG_TYPES.has(msg_type)) {
        sendError(ws, 'validation_error', 'סוג הודעה לא תקין');
        return;
      }
      if (peer_id === userId) {
        sendError(ws, 'validation_error', 'לא ניתן לשלוח הודעה לעצמך');
        return;
      }
      if (!profileQueries.findById(peer_id)) {
        sendError(ws, 'not_found', 'המשתמש לא נמצא');
        return;
      }
      if (MessageModel.isBlocked(userId, peer_id)) {
        sendError(ws, 'blocked', 'לא ניתן לשלוח הודעה למשתמש זה');
        return;
      }

      let msg;
      try {
        msg = MessageModel.send(userId, peer_id, trimmedContent, msg_type);
      } catch (err) {
        console.error('[ws] failed to persist message', err);
        sendError(ws, 'internal_error', 'אירעה שגיאה, נסה שוב מאוחר יותר');
        return;
      }

      // Acknowledge sender
      ws.send(JSON.stringify({ type: 'ack', message_id: msg.message_id }));

      // Deliver to recipient
      const delivered = wsManager.send(peer_id, msg);

      // Push notification if recipient is offline
      if (!delivered) {
        const recipientProfile = profileQueries.findById(peer_id);
        if (recipientProfile?.expo_push_token) {
          const senderCreds = authQueries.findById(userId);
          const senderName  = profileQueries.findById(userId)?.name ?? senderCreds?.username ?? 'משתמש';
          const preview     = trimmedContent.length > 60 ? trimmedContent.slice(0, 60) + '…' : trimmedContent;
          sendPushNotification(recipientProfile.expo_push_token, senderName, preview, userId);
        }
      }
    });

    // ── Cleanup ───────────────────────────────────────────────────────────────
    ws.on('close', () => {
      wsManager.unregister(userId, ws);
    });
  });

  console.log('[ws] server attached at /ws');
}
