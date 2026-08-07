import axios from 'axios';
import { checkServerHealth } from '../../mobile/src/utils/checkServerHealth';

jest.mock('axios');
const getMock = axios.get as jest.Mock;

beforeEach(() =>
{
    getMock.mockReset();
});

describe('checkServerHealth', () =>
{
    it('returns true when the server responds with {ok: true}', async () =>
    {
        getMock.mockResolvedValue({ data: { ok: true } });

        const result = await checkServerHealth('http://192.168.1.5:3000');

        expect(result).toBe(true);
        expect(getMock).toHaveBeenCalledWith(
            'http://192.168.1.5:3000/api/health',
            expect.objectContaining({ timeout: expect.any(Number) }),
        );
    });

    it('returns false when the server responds but not with {ok: true}', async () =>
    {
        getMock.mockResolvedValue({ data: { ok: false } });

        expect(await checkServerHealth('http://192.168.1.5:3000')).toBe(false);
    });

    it('returns false when the response body has no ok field at all', async () =>
    {
        getMock.mockResolvedValue({ data: {} });

        expect(await checkServerHealth('http://192.168.1.5:3000')).toBe(false);
    });

    it('returns false (never throws) when the request fails outright — unreachable host', async () =>
    {
        getMock.mockRejectedValue(new Error('Network Error'));

        await expect(checkServerHealth('http://not-a-real-host:3000')).resolves.toBe(false);
    });

    it('returns false (never throws) on a timeout', async () =>
    {
        const timeoutError = Object.assign(new Error('timeout of 8000ms exceeded'), { code: 'ECONNABORTED' });
        getMock.mockRejectedValue(timeoutError);

        await expect(checkServerHealth('http://192.168.1.5:3000')).resolves.toBe(false);
    });
});
