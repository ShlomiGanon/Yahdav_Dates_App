// Every backend response is HTTP 200; success/failure is signaled by this
// envelope's `success` boolean, with a human-readable `message` the
// frontend can show directly. `error` is a stable machine-readable code
// (present on failure) — e.g. used to detect "unauthorized" specifically
// for the auto-refresh interceptor.
export interface ApiEnvelope
{
    success: boolean;
    message: string;
    error?:  string;
}
