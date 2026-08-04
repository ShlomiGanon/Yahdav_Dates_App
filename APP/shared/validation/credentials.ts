export type ValidationError = string | null;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateEmail(email: string): ValidationError
{
    if (!EMAIL_RE.test(email.trim()))
    {
        return 'invalid_email';
    }
    return null;
}

export function validatePassword(password: string): ValidationError
{
    if (password.length < 8)
    {
        return 'password_too_short';
    }
    return null;
}

export function validatePasswordsMatch(password: string, confirm: string): ValidationError
{
    if (password !== confirm)
    {
        return 'passwords_dont_match';
    }
    return null;
}

const USERNAME_MIN = 3;
const USERNAME_MAX = 30;
const USERNAME_RE = /^[a-zA-Z0-9_]+$/;

export function validateUsername(username: string): ValidationError
{
    if (username.length < USERNAME_MIN || username.length > USERNAME_MAX)
    {
        return 'username_invalid_length';
    }
    if (!USERNAME_RE.test(username))
    {
        return 'username_invalid_characters';
    }
    return null;
}

// Derives a username from an email's local-part (strip domain, sanitize to
// the allowed charset, lowercase, cap at the max length). Short local-parts
// (e.g. "a1@x.com") are padded up to the minimum length with '0' rather
// than silently producing a username that fails validateUsername's own
// length check on the very next line the caller runs it through.
export function deriveUsername(email: string): string
{
    const stripped = (email.split('@')[0] ?? '')
        .replace(/[^a-zA-Z0-9_]/g, '')
        .toLowerCase()
        .slice(0, USERNAME_MAX);

    return stripped.length >= USERNAME_MIN
        ? stripped
        : stripped.padEnd(USERNAME_MIN, '0');
}
