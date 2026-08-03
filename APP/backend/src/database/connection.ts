import { DatabaseSync } from 'node:sqlite';
import path from 'path';
import fs from 'fs';
import { config } from '../config';

let _db: DatabaseSync | null = null;

export function getDb(): DatabaseSync {
  if (_db) return _db;

  const isMemory = config.dbPath === ':memory:';
  const dbPath   = isMemory ? ':memory:' : path.resolve(config.dbPath);
  if (!isMemory) fs.mkdirSync(path.dirname(dbPath), { recursive: true });

  _db = new DatabaseSync(dbPath);
  _db.exec('PRAGMA journal_mode=WAL');
  _db.exec('PRAGMA foreign_keys=ON');
  _db.exec('PRAGMA busy_timeout=5000');

  return _db;
}

export function closeDb(): void {
  if (_db) { _db.close(); _db = null; }
}
