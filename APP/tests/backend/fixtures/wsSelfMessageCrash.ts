// Standalone fixture, run as a CHILD PROCESS (never imported into the main
// Jest run) by security.test.ts's TC-1308 regression test. It reproduces
// improve.md's "unhandled synchronous exception in the WS handler can crash
// the process" finding: wsServer.ts's `ws.on('message', ...)` callback has
// no try/catch around MessageModel.send(), and a self-message (peer_id ===
// sender) violates the `direct_messages` CHECK constraint, throwing
// synchronously outside of Express's request stack — where nothing catches
// it. Running this in a disposable child process lets the test assert on
// the exit code without risking the actual Jest worker.
//
// Required env vars (DB_PATH, JWT_SECRET, etc.) are set by the caller via
// the child process's environment — NOT as top-level statements in this
// file. `import` declarations are hoisted above other top-level code, so
// assignments to `process.env` written before these imports would still run
// *after* them, too late for config.ts's `required()` check.

import http from 'http';
import WebSocket from 'ws';
import { createApp } from '../../../backend/src/app';
import { runMigrations } from '../../../backend/src/database/migrate';
import { attachWsServer } from '../../../backend/src/websocket/wsServer';
import { UserModel } from '../../../backend/src/models/UserModel';
import { SessionModel } from '../../../backend/src/models/SessionModel';

async function main(): Promise<void>
{
  runMigrations();
  const app = createApp();
  const server = http.createServer(app);
  attachWsServer(server);

  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = (server.address() as { port: number }).port;

  const userId = await UserModel.register({
    username: 'crashfixtureuser',
    email: 'crashfixture@test.com',
    password: 'Password123!',
    name: '', gender: '', date_of_birth: '', city: '', region: '',
  });
  const { access_token } = SessionModel.issue(userId, false);

  const ws = new WebSocket(`ws://127.0.0.1:${port}/ws?token=${access_token}`);

  await new Promise<void>((resolve, reject) =>
  {
    ws.once('open', () => resolve());
    ws.once('error', reject);
  });

  // The trigger: a message frame where peer_id is the sender's own id.
  ws.send(JSON.stringify({ peer_id: userId, content: 'talking to myself' }));

  // Give the (buggy) synchronous throw time to propagate to an
  // uncaughtException and kill the process. If we're still alive after
  // this, the handler survived the bad input.
  await new Promise((resolve) => setTimeout(resolve, 1000));

  console.log('ALIVE');
  process.exit(0);
}

main().catch((err) =>
{
  console.error('FIXTURE_ERROR', err);
  process.exit(2);
});
