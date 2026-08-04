// Every backend response is HTTP 200; success/failure is signaled by this
// envelope's `success` boolean, with a human-readable Hebrew `message` the
// UI can show directly. `error` is a stable machine-readable code (present
// on failure) — used by the axios interceptor to detect "unauthorized"
// specifically, distinct from other business-logic failures.
export type ApiEnvelope = {
  success: boolean;
  message: string;
  error?: string;
};
