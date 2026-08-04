import { serverMessage } from '../../../shared/copy/server';
import { he } from '../../../shared/copy/server/locales/he';

// The full set of codes actually passed to fail(res, code) across the
// backend (grepped from src/, including the two thrown dynamically by
// SessionModel and re-passed to fail() in auth.routes.ts's /refresh
// handler) — a completeness check that every code the backend can
// actually emit has a matching dictionary entry.
const CODES_USED_BY_BACKEND =
[
    'internal_error',
    'unauthorized',
    'forbidden',
    'email_taken',
    'username_taken',
    'invalid_credentials',
    'missing_refresh_token',
    'invalid_token',
    'not_found',
    'validation_error',
    'blocked',
    'cannot_change_own_status',
    'cannot_delete_self',
    'invalid_file_type',
    'file_too_large',
    'missing_file',
    'photo_limit_reached',
    'cannot_block_self',
    'session_not_found',
    'session_expired',
];

describe('serverMessage', () =>
{
    it('resolves every key in the he dictionary to its own text', () =>
    {
        for (const key of Object.keys(he))
        {
            expect(serverMessage(key)).toBe((he as Record<string, string>)[key]);
        }
    });

    it('has a dictionary entry for every code the backend actually emits', () =>
    {
        for (const code of CODES_USED_BY_BACKEND)
        {
            expect(he).toHaveProperty(code);
        }
    });

    it('falls back to a generic message for an unknown code', () =>
    {
        expect(serverMessage('not_a_real_code')).toBe('אירעה שגיאה, נסה שוב מאוחר יותר');
    });
});
