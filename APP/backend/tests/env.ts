// Runs before each test file (setupFiles). Sets env vars before any module is loaded.
process.env.DB_PATH             = ':memory:';
process.env.JWT_SECRET          = 'test-secret-key-for-jest-only';
process.env.JWT_ACCESS_TTL      = '15m';
process.env.JWT_REFRESH_TTL_DAYS = '30';
process.env.UPLOADS_DIR         = '/tmp/yahdav-test-uploads';
process.env.PORT                = '0';
