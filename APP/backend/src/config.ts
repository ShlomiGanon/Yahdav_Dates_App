import 'dotenv/config';

function required(key: string): string {
  const val = process.env[key];
  if (!val) throw new Error(`Missing required env var: ${key}`);
  return val;
}

function optional(key: string, fallback: string): string {
  return process.env[key] ?? fallback;
}

export const config = {
  port:              parseInt(optional('PORT', '3000'), 10),
  dbPath:            optional('DB_PATH',       'data/yahdav.sqlite3'),
  uploadsDir:        optional('UPLOADS_DIR',   'data/uploads'),
  jwtSecret:         required('JWT_SECRET'),
  jwtAccessTtl:      optional('JWT_ACCESS_TTL', '15m'),
  jwtRefreshTtlDays: parseInt(optional('JWT_REFRESH_TTL_DAYS', '30'), 10),
  // Comma-separated list of allowed browser origins (web + admin dashboards).
  // ADMIN_CORS_ORIGIN is kept as the env var name for backward compatibility
  // with existing deploys/docs, but now accepts a comma-separated list.
  corsOrigins: optional('ADMIN_CORS_ORIGIN', 'http://localhost:5173,http://localhost:5174')
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean),
  expoPushUrl:       optional('EXPO_PUSH_URL', 'https://exp.host/--/api/v2/push/send'),
} as const;
