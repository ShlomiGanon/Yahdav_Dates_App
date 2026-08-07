import axios from 'axios';

const HEALTH_CHECK_TIMEOUT_MS = 8000;

// Validates a candidate server URL by hitting /api/health directly with a
// raw axios call — not through the app's shared api client, since that's
// not configured with this URL yet (this call is what decides whether it
// should be). A short timeout so an unreachable host fails fast instead of
// hanging the gate screen indefinitely. Only used by the dev-build
// server-URL gate (see components/ServerUrlGate.tsx).
export async function checkServerHealth(baseUrl: string): Promise<boolean>
{
    try
    {
        const { data } = await axios.get(`${baseUrl}/api/health`, { timeout: HEALTH_CHECK_TIMEOUT_MS });
        return data?.ok === true;
    }
    catch
    {
        return false;
    }
}
