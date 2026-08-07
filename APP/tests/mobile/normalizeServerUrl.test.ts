import { normalizeServerUrl } from '../../mobile/src/utils/normalizeServerUrl';

describe('normalizeServerUrl', () =>
{
    it('prepends http:// when no scheme is given', () =>
    {
        expect(normalizeServerUrl('192.168.1.5:3000')).toBe('http://192.168.1.5:3000');
    });

    it('leaves an existing http:// scheme untouched', () =>
    {
        expect(normalizeServerUrl('http://192.168.1.5:3000')).toBe('http://192.168.1.5:3000');
    });

    it('leaves an existing https:// scheme untouched, does not force http://', () =>
    {
        expect(normalizeServerUrl('https://api.example.com')).toBe('https://api.example.com');
    });

    it('is case-insensitive when detecting an existing scheme', () =>
    {
        expect(normalizeServerUrl('HTTP://192.168.1.5:3000')).toBe('HTTP://192.168.1.5:3000');
    });

    it('trims a single trailing slash', () =>
    {
        expect(normalizeServerUrl('http://192.168.1.5:3000/')).toBe('http://192.168.1.5:3000');
    });

    it('trims multiple trailing slashes', () =>
    {
        expect(normalizeServerUrl('http://192.168.1.5:3000///')).toBe('http://192.168.1.5:3000');
    });

    it('trims surrounding whitespace before processing', () =>
    {
        expect(normalizeServerUrl('  192.168.1.5:3000  ')).toBe('http://192.168.1.5:3000');
    });

    it('combines scheme-prepending and trailing-slash trimming', () =>
    {
        expect(normalizeServerUrl('192.168.1.5:3000/')).toBe('http://192.168.1.5:3000');
    });

    it('returns an empty string unchanged (no scheme prepended to nothing)', () =>
    {
        expect(normalizeServerUrl('')).toBe('');
    });

    it('returns an empty string for whitespace-only input', () =>
    {
        expect(normalizeServerUrl('   ')).toBe('');
    });
});
