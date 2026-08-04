import { clientMessage } from '../../../shared/copy/client';
import { he } from '../../../shared/copy/client/locales/he';
import
{
    validateEmail,
    validatePassword,
    validatePasswordsMatch,
    validateUsername,
} from '../../../shared/validation/credentials';
import { validateRequired, validateDateOfBirth } from '../../../shared/validation/profile';

describe('clientMessage', () =>
{
    it('resolves every key in the he dictionary to its own text', () =>
    {
        for (const key of Object.keys(he) as Array<keyof typeof he>)
        {
            expect(clientMessage(key)).toBe(he[key]);
        }
    });

    it('every code producible by @shared/validation/profile has a matching dictionary entry', () =>
    {
        expect(validateRequired('')).not.toBeNull();
        // validateRequired's own code (missing_required_field) isn't in the
        // client dictionary by design — profile forms show field-specific
        // messages (name_required, city_required, ...) instead of one
        // generic message, matching the current, unchanged UI behavior.

        expect(he).toHaveProperty('invalid_date');
        expect(he).toHaveProperty('age_too_young');
        expect(he).toHaveProperty('age_too_old');

        expect(validateDateOfBirth('not-a-date')).toBe('invalid_date');
        expect(validateDateOfBirth('2050-01-01')).toBe('age_too_young');
        expect(validateDateOfBirth('1900-01-01')).toBe('age_too_old');
    });

    it('every code producible by @shared/validation/credentials that the client actually displays has a matching entry', () =>
    {
        // password_too_short and passwords_dont_match are shown directly by
        // web/mobile signup forms today — must have entries.
        expect(validatePassword('short')).toBe('password_too_short');
        expect(he).toHaveProperty('password_too_short');

        expect(validatePasswordsMatch('a', 'b')).toBe('passwords_dont_match');
        expect(he).toHaveProperty('passwords_dont_match');

        // invalid_email / username_invalid_* are validated but never
        // rendered from a hardcoded client string today (no username field
        // in the UI at all; email format is only checked server-side) — no
        // client dictionary entry expected for these.
        expect(validateEmail('not-an-email')).toBe('invalid_email');
        expect(validateUsername('ab')).toBe('username_invalid_length');
    });
});
