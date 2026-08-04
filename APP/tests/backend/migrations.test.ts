import fs from 'fs';
import path from 'path';
import { runMigrations } from '../../backend/src/database/migrate';
import { getDb, closeDb } from '../../backend/src/database/connection';

// tests.md section 18 (TC-1803/1804) — the migration runner's own regression
// coverage. Deliberately isolated in its own file so Jest gives it a fresh
// module registry (and therefore a fresh connection.ts `_db` singleton),
// independent of every other test file's shared app/db.

const MIGRATIONS_DIR = path.join(__dirname, '../../backend/migrations');
const DUMMY_MIGRATION_PATH = path.join(MIGRATIONS_DIR, '002_test_regression_dummy.sql');

afterEach(() =>
{
  if (fs.existsSync(DUMMY_MIGRATION_PATH))
  {
    fs.unlinkSync(DUMMY_MIGRATION_PATH);
  }
  closeDb();
});

describe('runMigrations', () =>
{
  it('TC-1804 running migrations twice against an already-migrated DB is a no-op', () =>
  {
    runMigrations();
    runMigrations();

    const row = getDb().prepare('SELECT COUNT(*) as cnt FROM schema_version').get() as { cnt: number };
    expect(row.cnt).toBe(1);
  });

  // Regression test for the improve.md finding: migrate.ts captures the
  // `schema_version` row ONCE before the loop and never reassigns it, so
  // every pending migration after the first still sees `row === undefined`
  // and takes the INSERT branch instead of UPDATE — leaving duplicate rows
  // in schema_version (no PK on that table) when 2+ files are pending in a
  // single run. This is written to assert the CORRECT behavior, so it fails
  // today against the real bug and will start (unexpectedly) passing the
  // moment someone fixes migrate.ts — at which point `.failing` should be
  // removed and this becomes a normal assertion.
  it.failing('TC-1803 applying two pending migrations in one run leaves exactly one schema_version row', () =>
  {
    fs.writeFileSync(
      DUMMY_MIGRATION_PATH,
      'CREATE TABLE __test_regression_dummy (id INTEGER);\n',
    );

    runMigrations();

    const row = getDb().prepare('SELECT COUNT(*) as cnt FROM schema_version').get() as { cnt: number };
    expect(row.cnt).toBe(1);
  });
});
