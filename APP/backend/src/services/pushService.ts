import https from 'https';
import { config } from '../config';

interface PushPayload {
  to:      string;
  title:   string;
  body:    string;
  sound:   string;
  data:    Record<string, unknown>;
}

// Fire-and-forget — never throws, errors are logged only.
export function sendPushNotification(
  expoToken:   string,
  senderName:  string,
  preview:     string,
  peerId:      string,
): void {
  const payload: PushPayload = {
    to:    expoToken,
    title: 'הודעה חדשה',
    body:  `${senderName}: ${preview}`,
    sound: 'default',
    data:  { peer_id: peerId, screen: 'chat' },
  };

  const body = JSON.stringify(payload);
  const url  = new URL(config.expoPushUrl);

  const req = https.request(
    {
      hostname: url.hostname,
      path:     url.pathname,
      method:   'POST',
      headers:  {
        'Content-Type':   'application/json',
        'Content-Length': Buffer.byteLength(body),
      },
    },
    (res) => {
      // Drain response to free socket
      res.resume();
      if (res.statusCode && res.statusCode >= 400) {
        console.error(`[push] HTTP ${res.statusCode} for token ${expoToken.slice(0, 20)}…`);
      }
    },
  );

  req.on('error', (err) => {
    console.error('[push] request error:', err.message);
  });

  req.write(body);
  req.end();
}
