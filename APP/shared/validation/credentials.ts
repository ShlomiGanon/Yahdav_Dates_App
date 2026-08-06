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

export type LoginFormError = 'missing_all_fields';

// The login form's single pre-flight check — was duplicated identically in
// mobile's LoginScreen.tsx and web's LoginPage.tsx. Deliberately narrow
// scope per the report: the rest of each screen's submit orchestration
// (call login(), navigate on success, network-error catch) stays
// duplicated — the navigation call itself differs per platform and isn't
// worth abstracting for one pre-flight check. See APP/review.md
// finding 2.9.
export function validateLoginForm(identifier: string, password: string): LoginFormError | null
{
    if (!identifier.trim() || !password)
    {
        return 'missing_all_fields';
    }

    return null;
}

export type SignupFormError =
    | 'missing_all_fields'
    | 'passwords_dont_match'
    | 'password_too_short';

export interface SignupFormInput
{
    email:    string;
    password: string;
    confirm:  string;
}

// The signup form's validation precedence — was duplicated identically
// (same order, same clientMessage keys) in mobile's SignupScreen.tsx and
// web's SignupPage.tsx. Note this never validates email format, only
// presence — matching both screens' actual current behavior. See
// APP/review.md finding 2.10.
export function validateSignupForm(input: SignupFormInput): SignupFormError | null
{
    if (!input.email.trim() || !input.password || !input.confirm)
    {
        return 'missing_all_fields';
    }

    if (validatePasswordsMatch(input.password, input.confirm))
    {
        return 'passwords_dont_match';
    }

    if (validatePassword(input.password))
    {
        return 'password_too_short';
    }

    return null;
}
