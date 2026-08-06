// Peer-facing gender label ('זכר'/'נקבה'/'אחר') — was duplicated identically
// across mobile's PeerProfileScreen.tsx and web's PeerProfilePage.tsx before
// this consolidation. Distinct from the gendered word choice inside
// formatCandidateMeta.ts's segments ('בן'/'בת'/'בן/בת'), which is a
// different label for a different context and stays separate — see
// APP/review.md finding 2.5.
export function genderLabel(gender: string | null): string | null
{
    if (gender === 'male')
    {
        return 'זכר';
    }

    if (gender === 'female')
    {
        return 'נקבה';
    }

    if (gender === 'other')
    {
        return 'אחר';
    }

    return null;
}
