// Computes age in whole years from a date-of-birth string. Returns null for
// unparseable input or a clearly-invalid date (a zeroed/garbage date on or
// before 1900). Was duplicated identically across mobile's
// PeerProfileScreen.tsx, web's PeerProfilePage.tsx, and
// shared/utils/formatCandidateMeta.ts before this consolidation — see
// APP/review.md finding 2.5. A fourth, structurally different age
// calculation lives in shared/validation/profile.ts's validateDateOfBirth
// (no Math.floor, a different validity guard) and was deliberately left
// alone — see that finding's DONE note for why.
export function calcAge(dob: string | null): number | null
{
    if (!dob)
    {
        return null;
    }

    const d = new Date(dob);

    if (isNaN(d.getTime()) || d.getFullYear() <= 1900)
    {
        return null;
    }

    return Math.floor((Date.now() - d.getTime()) / (365.25 * 24 * 3600 * 1000));
}
