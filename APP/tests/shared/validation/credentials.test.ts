import
{
    validateEmail,
    validatePassword,
    validatePasswordsMatch,
    validateUsername,
    deriveUsername,
} from '../../../shared/validation/credentials';

describe('validateEmail', () =>
{
    it('accepts a well-formed email', () =>
    {
        expect(validateEmail('user@example.com')).toBeNull();
    });

    it.each(
    [
        'not-an-email',
        'missing-domain@',
        '@missing-local.com',
        'spaces in@email.com',
    ])('rejects "%s"', (input) =>
    {
        expect(validateEmail(input)).toBe('invalid_email');
    });
});

describe('validatePassword', () =>
{
    it('rejects a 7-character password', () =>
    {
        expect(validatePassword('1234567')).toBe('password_too_short');
    });

    it('accepts an 8-character password', () =>
    {
        expect(validatePassword('12345678')).toBeNull();
    });
});

describe('validatePasswordsMatch', () =>
{
    it('rejects mismatched passwords', () =>
    {
        expect(validatePasswordsMatch('abc12345', 'abc12346')).toBe('passwords_dont_match');
    });

    it('accepts matching passwords', () =>
    {
        expect(validatePasswordsMatch('abc12345', 'abc12345')).toBeNull();
    });
});

describe('validateUsername', () =>
{
    it('rejects a 2-character username (too short)', () =>
    {
        expect(validateUsername('ab')).toBe('username_invalid_length');
    });

    it('accepts a 3-character username (minimum)', () =>
    {
        expect(validateUsername('abc')).toBeNull();
    });

    it('accepts a 30-character username (maximum)', () =>
    {
        expect(validateUsername('a'.repeat(30))).toBeNull();
    });

    it('rejects a 31-character username (too long)', () =>
    {
        expect(validateUsername('a'.repeat(31))).toBe('username_invalid_length');
    });

    it('rejects a username containing a space', () =>
    {
        expect(validateUsername('bad username')).toBe('username_invalid_characters');
    });

    it('rejects a username containing a hyphen', () =>
    {
        expect(validateUsername('bad-user')).toBe('username_invalid_characters');
    });

    it('rejects a username containing non-Latin characters', () =>
    {
        expect(validateUsername('משתמש')).toBe('username_invalid_characters');
    });
});

describe('deriveUsername', () =>
{
    it('strips the domain and lowercases', () =>
    {
        expect(deriveUsername('SomeUser@Example.com')).toBe('someuser');
    });

    it('strips disallowed characters', () =>
    {
        expect(deriveUsername('some.user+tag@example.com')).toBe('someusertag');
    });

    it('caps at 30 characters', () =>
    {
        const longLocal = 'a'.repeat(40);
        expect(deriveUsername(`${longLocal}@example.com`)).toHaveLength(30);
    });

    // This is the bug found during planning: a short email local-part used
    // to derive a username shorter than validateUsername's own 3-char
    // minimum, so the backend would reject it with a message about a field
    // the user never saw or typed.
    it('pads a short local-part up to the 3-character minimum', () =>
    {
        const derived = deriveUsername('a1@x.com');
        expect(derived).toBe('a10');
        expect(validateUsername(derived)).toBeNull();
    });

    it('pads a single-character local-part up to the minimum', () =>
    {
        const derived = deriveUsername('a@x.com');
        expect(derived.length).toBeGreaterThanOrEqual(3);
        expect(validateUsername(derived)).toBeNull();
    });
});
