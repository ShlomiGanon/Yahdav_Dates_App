import fs from 'fs';
import path from 'path';
import { getDb } from './connection';

const MIGRATIONS_DIR = path.resolve('migrations');

export function runMigrations(): void {
  const db = getDb();

  db.exec(`
    CREATE TABLE IF NOT EXISTS schema_version (
      version INTEGER NOT NULL
    )
  `);

  const row = db.prepare('SELECT version FROM schema_version').get() as { version: number } | undefined;
  let current = row?.version ?? 0;

  const files = fs
    .readdirSync(MIGRATIONS_DIR)
    .filter(f => /^\d{3}_.*\.sql$/.test(f))
    .sort();

  for (const file of files) {
    const version = parseInt(file.slice(0, 3), 10);
    if (version <= current) continue;

    const sql = fs.readFileSync(path.join(MIGRATIONS_DIR, file), 'utf8');
    db.exec(sql);

    if (row === undefined) {
      db.prepare('INSERT INTO schema_version (version) VALUES (?)').run(version);
    } else {
      db.prepare('UPDATE schema_version SET version = ?').run(version);
    }

    current = version;
    console.log(`[migrate] applied ${file}`);
  }

  if (current === (row?.version ?? 0)) {
    console.log('[migrate] schema up to date');
  }
}

// Run directly: tsx src/database/migrate.ts
if (require.main === module) {
  runMigrations();
}
