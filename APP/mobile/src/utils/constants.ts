export const WS_RECONNECT = {
  INITIAL_DELAY_MS: 1_000,
  MAX_DELAY_MS:     30_000,
  BACKOFF_FACTOR:   2,
  MAX_ATTEMPTS:     10,
} as const;
