// Prepends http:// when the user typed an address with no scheme (e.g.
// "192.168.1.5:3000" — the common case on a local network), and trims any
// trailing slash, so "http://host:3000/" and "host:3000" both end up as
// the same normalized "http://host:3000" before being saved or used as
// the API client's baseURL. Only used by the dev-build server-URL gate
// (see components/ServerUrlGate.tsx) — production never calls this.
export function normalizeServerUrl(raw: string): string
{
    const trimmed = raw.trim();

    if (!trimmed)
    {
        return trimmed;
    }

    const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;

    return withScheme.replace(/\/+$/, '');
}
