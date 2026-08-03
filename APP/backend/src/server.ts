import http from 'http';
import { createApp } from './app';
import { config } from './config';
import { runMigrations } from './database/migrate';
import { attachWsServer } from './websocket/wsServer';

async function main() {
  runMigrations();

  const app    = createApp();
  const server = http.createServer(app);

  attachWsServer(server);

  server.listen(config.port, () => {
    console.log(`[server] listening on http://localhost:${config.port}`);
  });
}

main().catch(err => {
  console.error('[server] fatal:', err);
  process.exit(1);
});
