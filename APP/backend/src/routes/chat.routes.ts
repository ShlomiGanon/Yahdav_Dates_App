import { Router, Request, Response } from 'express';
import { param, query, body, validationResult } from 'express-validator';
import { authenticate, AuthRequest } from '../middleware/authenticate';
import { MessageModel } from '../models/MessageModel';
import { wsManager } from '../websocket/wsManager';
import { profileQueries } from '../database/queries/profile.queries';
import { authQueries } from '../database/queries/auth.queries';
import { sendPushNotification } from '../services/pushService';
import { ok, fail, failValidation } from '../utils/responses';

const router = Router();
router.use(authenticate);

// ── GET /chat/conversations ───────────────────────────────────────────────────

router.get('/conversations', (req: Request, res: Response): void => {
  const { sub } = (req as AuthRequest).user;
  ok(res, { conversations: MessageModel.getConversations(sub) });
});

// ── GET /chat/:peer_id?limit=&before= ────────────────────────────────────────

const getMessagesRules = [
  param('peer_id').isUUID().withMessage('מזהה משתמש לא תקין'),
  query('limit').optional().isInt({ min: 1, max: 100 }).toInt()
    .withMessage('מספר התוצאות חייב להיות בין 1 ל-100'),
  query('before').optional().isUUID().withMessage('פרמטר עמוד לא תקין'),
];

router.get('/:peer_id', getMessagesRules, (req: Request, res: Response): void => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

  const { sub } = (req as AuthRequest).user;
  const limit   = (req.query.limit as unknown as number) || 20;
  const before  = req.query.before as string | undefined;

  ok(res, { messages: MessageModel.getMessages(sub, req.params.peer_id, limit, before) });
});

// ── POST /chat/:peer_id ───────────────────────────────────────────────────────

const sendRules = [
  param('peer_id').isUUID().withMessage('מזהה משתמש לא תקין'),
  body('content').trim().notEmpty().withMessage('יש להזין תוכן הודעה')
    .bail()
    .isLength({ max: 4000 }).withMessage('ההודעה ארוכה מדי (מקסימום 4000 תווים)'),
  body('msg_type').optional().isIn(['TEXT', 'AUDIO', 'IMAGE']).withMessage('סוג הודעה לא תקין'),
];

router.post('/:peer_id', sendRules, (req: Request, res: Response): void => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

  const { sub } = (req as AuthRequest).user;
  const peerId  = req.params.peer_id;

  if (sub === peerId) { fail(res, 'validation_error', { message: 'לא ניתן לשלוח הודעה לעצמך' }); return; }
  if (!profileQueries.findById(peerId)) { fail(res, 'not_found'); return; }

  if (MessageModel.isBlocked(sub, peerId)) {
    fail(res, 'blocked');
    return;
  }

  const msg = MessageModel.send(sub, peerId, req.body.content, req.body.msg_type ?? 'TEXT');

  // Best-effort WS delivery + push if offline
  const delivered = wsManager.send(peerId, msg);
  if (!delivered) {
    const recipientProfile = profileQueries.findById(peerId);
    if (recipientProfile?.expo_push_token) {
      const senderName = profileQueries.findById(sub)?.name ?? authQueries.findById(sub)?.username ?? 'משתמש';
      const preview    = msg.content.length > 60 ? msg.content.slice(0, 60) + '…' : msg.content;
      sendPushNotification(recipientProfile.expo_push_token, senderName, preview, sub);
    }
  }

  ok(res, { ...msg }, 'ההודעה נשלחה');
});

// ── PUT /chat/:peer_id/read ───────────────────────────────────────────────────

router.put(
  '/:peer_id/read',
  [param('peer_id').isUUID().withMessage('מזהה משתמש לא תקין')],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

    const { sub } = (req as AuthRequest).user;
    MessageModel.markRead(sub, req.params.peer_id);
    ok(res, {}, 'ההודעות סומנו כנקראו');
  },
);

export default router;
