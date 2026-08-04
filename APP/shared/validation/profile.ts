export type ValidationError = string | null;

export function validateRequired(value: string): ValidationError
{
    if (!value.trim())
    {
        return 'missing_required_field';
    }
    return null;
}

const MIN_AGE = 18;
const MAX_AGE = 100;
const MS_PER_YEAR = 1000 * 60 * 60 * 24 * 365.25;

// Accepts a YYYY-MM-DD date-of-birth string. Validates both that the date
// actually exists (catches e.g. "2024-02-30" silently rolling over to
// March 2nd — plain isNaN(parsed.getTime()) alone doesn't catch this) and
// that the resulting age falls within [MIN_AGE, MAX_AGE].
export function validateDateOfBirth(dateOfBirth: string): ValidationError
{
    const parsed = new Date(dateOfBirth);
    const day = parseInt(dateOfBirth.split('-')[2] ?? '', 10);

    if (isNaN(parsed.getTime()) || parsed.getDate() !== day)
    {
        return 'invalid_date';
    }

    const age = (Date.now() - parsed.getTime()) / MS_PER_YEAR;

    if (age < MIN_AGE)
    {
        return 'age_too_young';
    }
    if (age > MAX_AGE)
    {
        return 'age_too_old';
    }

    return null;
}
