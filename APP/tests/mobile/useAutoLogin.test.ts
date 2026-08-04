jest.mock('../../mobile/src/api/axios', () => ({
  api: { get: jest.fn() },
}));

jest.mock('../../mobile/src/auth/storage', () => ({
  loadTokens: jest.fn(),
  clearTokens: jest.fn(),
}));

import { renderHook, waitFor } from '@testing-library/react-native';
import { api } from '../../mobile/src/api/axios';
import { loadTokens, clearTokens } from '../../mobile/src/auth/storage';
import { useAutoLogin } from '../../mobile/src/auth/useAutoLogin';

const apiGetMock = api.get as jest.Mock;
const loadTokensMock = loadTokens as jest.Mock;
const clearTokensMock = clearTokens as jest.Mock;

const FAKE_USER = {
  user_id: 'u1',
  email: 'a@test.com',
  username: 'a',
  is_admin: false,
};

beforeEach(() =>
{
  apiGetMock.mockReset();
  loadTokensMock.mockReset();
  clearTokensMock.mockReset();
});

describe('useAutoLogin', () =>
{
  it('TC-506 silently logs in when a valid session is stored and /auth/me succeeds', async () =>
  {
    loadTokensMock.mockResolvedValue({ access: 'a1', refresh: 'r1' });
    apiGetMock.mockResolvedValue({ data: FAKE_USER });

    // renderHook() is async in @testing-library/react-native v14.
    const { result } = await renderHook(() => useAutoLogin());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.user).toEqual(FAKE_USER);
    expect(clearTokensMock).not.toHaveBeenCalled();
  });

  it('does not call /auth/me at all when no tokens are stored', async () =>
  {
    loadTokensMock.mockResolvedValue({ access: null, refresh: null });

    const { result } = await renderHook(() => useAutoLogin());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(apiGetMock).not.toHaveBeenCalled();
    expect(result.current.user).toBeNull();
  });

  it('TC-507 clears tokens when the stored session is genuinely invalid (401)', async () =>
  {
    loadTokensMock.mockResolvedValue({ access: 'stale', refresh: 'stale' });
    const unauthorized = Object.assign(new Error('unauthorized'), { response: { status: 401 } });
    apiGetMock.mockRejectedValue(unauthorized);

    const { result } = await renderHook(() => useAutoLogin());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(clearTokensMock).toHaveBeenCalledTimes(1);
    expect(result.current.user).toBeNull();
  });

  // Regression test for improve.md Mobile High #2 / tests.md TC-505: a
  // network-layer failure (no `error.response` at all — the request never
  // reached the server) is currently treated identically to a real 401 by
  // the hook's single unconditional `catch { clearTokens() }`, wiping a
  // perfectly valid refresh token just because the device was briefly
  // offline at boot. Correct behavior is to leave stored tokens alone when
  // there's no server-confirmed rejection.
  it.failing('TC-505 does not clear tokens on a pure network failure (no response from server)', async () =>
  {
    loadTokensMock.mockResolvedValue({ access: 'a1', refresh: 'r1' });
    const networkError = Object.assign(new Error('Network Error'), { request: {} });
    apiGetMock.mockRejectedValue(networkError);

    const { result } = await renderHook(() => useAutoLogin());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(clearTokensMock).not.toHaveBeenCalled();
  });
});
