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

export type ProfileFormError =
    | 'name_required'
    | 'gender_required'
    | 'date_of_birth_required'
    | 'city_required'
    | 'invalid_date'
    | 'age_too_young'
    | 'age_too_old';

export interface ProfileFormInput
{
    name:          string;
    gender:        string | null;
    date_of_birth: string;   // '' if not yet fully specified by the caller
    city:          string;
}

// The profile-edit form's validation precedence — was duplicated identically
// (same order, same clientMessage keys) in mobile's ProfileScreen.tsx and
// web's ProfilePage.tsx. See APP/review.md finding 2.6.
export function validateProfileForm(input: ProfileFormInput): ProfileFormError | null
{
    if (!input.name.trim())
    {
        return 'name_required';
    }

    if (!input.gender)
    {
        return 'gender_required';
    }

    if (!input.date_of_birth)
    {
        return 'date_of_birth_required';
    }

    if (!input.city.trim())
    {
        return 'city_required';
    }

    return validateDateOfBirth(input.date_of_birth) as ProfileFormError | null;
}
