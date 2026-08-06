import
{
    validateRequired,
    validateDateOfBirth,
    validateProfileForm,
} from '../../../shared/validation/profile';

describe('validateRequired', () =>
{
    it('rejects an empty string', () =>
    {
        expect(validateRequired('')).toBe('missing_required_field');
    });

    it('rejects a whitespace-only string', () =>
    {
        expect(validateRequired('   ')).toBe('missing_required_field');
    });

    it('accepts a non-empty string', () =>
    {
        expect(validateRequired('תל אביב')).toBeNull();
    });
});

describe('validateDateOfBirth', () =>
{
    // validateDateOfBirth computes age using a 365.25-day-year approximation
    // (matching the original web/mobile logic being centralized here). A
    // calendar year subtracted naively (e.g. "same month/day, N years back")
    // can land on either side of an exact-N.0 boundary depending on which
    // specific leap years fall inside that span — so the boundary cases
    // below are constructed by day-count instead, landing safely on the
    // accepting side rather than exactly on the mathematical edge. The
    // non-boundary cases (17, 101) are far enough from any threshold that
    // simple calendar-year subtraction is unambiguous.
    function isoDateForAge(age: number): string
    {
        const now = new Date();
        const year = now.getFullYear() - age;
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    function isoDateDaysAgo(days: number): string
    {
        return new Date(Date.now() - days * 1000 * 60 * 60 * 24).toISOString().slice(0, 10);
    }

    it('rejects someone 17 years old (below minimum)', () =>
    {
        expect(validateDateOfBirth(isoDateForAge(17))).toBe('age_too_young');
    });

    it('accepts someone just past the 18-year minimum', () =>
    {
        expect(validateDateOfBirth(isoDateDaysAgo(6575))).toBeNull();
    });

    it('accepts someone just under the 100-year maximum', () =>
    {
        expect(validateDateOfBirth(isoDateDaysAgo(36524))).toBeNull();
    });

    it('rejects someone 101 years old (above maximum)', () =>
    {
        expect(validateDateOfBirth(isoDateForAge(101))).toBe('age_too_old');
    });

    it('rejects a garbage date string', () =>
    {
        expect(validateDateOfBirth('not-a-date')).toBe('invalid_date');
    });

    // The exact case web's own date check used to miss (isNaN alone isn't
    // enough): JS's Date silently rolls Feb 30 over to Mar 1/2 instead of
    // rejecting it outright.
    it('rejects February 30th as a rollover date, not a valid Feb/Mar date', () =>
    {
        expect(validateDateOfBirth('1990-02-30')).toBe('invalid_date');
    });

    it('accepts a real leap-day date of birth', () =>
    {
        expect(validateDateOfBirth('2000-02-29')).toBeNull();
    });
});

// Pins the exact validation precedence + exact clientMessage keys that were
// previously duplicated in mobile's ProfileScreen.tsx (validateAndSave) and
// web's ProfilePage.tsx (handleSave). Was verified against a local
// verbatim-copied reference implementation before validateProfileForm
// existed (see APP/review.md finding 2.6 for that pinning pass); these are
// the same assertions, now run against the real export.
describe('validateProfileForm', () =>
{
    const VALID =
    {
        name:          'ישראל ישראלי',
        gender:        'male',
        date_of_birth: '1995-06-15',
        city:          'תל אביב',
    };

    it('accepts a fully valid form', () =>
    {
        expect(validateProfileForm(VALID)).toBeNull();
    });

    it('rejects a missing name, ahead of every other field', () =>
    {
        expect(validateProfileForm({ ...VALID, name: '', gender: null, date_of_birth: '', city: '' })).toBe('name_required');
    });

    it('rejects a whitespace-only name', () =>
    {
        expect(validateProfileForm({ ...VALID, name: '   ' })).toBe('name_required');
    });

    it('rejects a missing gender once name is present, ahead of date/city', () =>
    {
        expect(validateProfileForm({ ...VALID, gender: null, date_of_birth: '', city: '' })).toBe('gender_required');
    });

    it('rejects a missing date of birth once name/gender are present, ahead of city', () =>
    {
        expect(validateProfileForm({ ...VALID, date_of_birth: '', city: '' })).toBe('date_of_birth_required');
    });

    it('rejects a missing city once name/gender/date are present', () =>
    {
        expect(validateProfileForm({ ...VALID, city: '' })).toBe('city_required');
    });

    it('rejects a whitespace-only city', () =>
    {
        expect(validateProfileForm({ ...VALID, city: '   ' })).toBe('city_required');
    });

    it('rejects an unparseable date of birth once all required fields are present', () =>
    {
        expect(validateProfileForm({ ...VALID, date_of_birth: 'not-a-date' })).toBe('invalid_date');
    });

    it('rejects an under-18 date of birth once all required fields are present', () =>
    {
        const now = new Date();
        const seventeen = `${now.getFullYear() - 17}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
        expect(validateProfileForm({ ...VALID, date_of_birth: seventeen })).toBe('age_too_young');
    });

    it('rejects an over-100 date of birth once all required fields are present', () =>
    {
        const now = new Date();
        const oneOhOne = `${now.getFullYear() - 101}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
        expect(validateProfileForm({ ...VALID, date_of_birth: oneOhOne })).toBe('age_too_old');
    });
});
