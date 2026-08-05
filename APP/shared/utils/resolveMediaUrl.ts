// Backend-stored media paths (Profile.photo_url, Photo.url, ...) are
// origin-relative — e.g. "/uploads/xxx.png" (see
// backend/src/routes/profile.routes.ts) — because the backend doesn't
// know its own public URL. Turning that into something a browser <img> or
// RN <Image> can actually fetch means joining it with whichever API base
// URL the *caller* is configured with; already-absolute paths (a future
// CDN URL, say) pass through untouched.
//
// Call this only from RemoteImage (web: components/RemoteImage.tsx,
// mobile: components/RemoteImage.tsx) — no other call site should reach
// for it directly. That's what makes "does this path still need
// resolving" a single, structural answer instead of a convention every
// screen has to remember.
export function resolveMediaUrl(path: string | null | undefined, baseUrl: string): string | null
{
    if (!path)
    {
        return null;
    }

    if (/^https?:\/\//i.test(path))
    {
        return path;
    }

    return `${baseUrl}${path}`;
}
