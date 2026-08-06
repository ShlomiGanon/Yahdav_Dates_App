import { calcAge } from './calcAge';

interface CandidateMetaInput
{
    date_of_birth: string | null;
    gender:        string | null;
    city:          string;
}

// The candidate-card meta line ("בן 28 · תל אביב") shown on both discovery
// surfaces — was two independent copies (mobile's DiscoverScreen.tsx, web's
// DiscoverPage.tsx) with identical age math, gendered word choice, and city
// fallback, differing only in how each platform joins the segments visually.
// Returns the ordered segments; each platform joins them with its own
// separator. See APP/review.md finding 2.4. Age math now delegates to
// calcAge.ts (finding 2.5) instead of duplicating it a third time.
export function formatCandidateMetaSegments(candidate: CandidateMetaInput): string[]
{
    const segments: string[] = [];
    const age = calcAge(candidate.date_of_birth);

    if (age !== null)
    {
        const word = candidate.gender === 'male' ? 'בן' : candidate.gender === 'female' ? 'בת' : 'בן/בת';
        segments.push(`${word} ${age}`);
    }

    if (candidate.city?.trim())
    {
        segments.push(candidate.city.trim());
    }

    return segments;
}

// Shown in place of the segments when a candidate has neither an age nor a
// city on file.
export const EMPTY_CANDIDATE_META_LABEL = 'חבר/ה חדש/ה';
