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

// The backend always answers HTTP 200; success/failure lives in the body
// (`{success, message, error?}`). Axios only rejects for genuine
// network-level failures now.

describe('useAutoLogin', () =>
{
  it('TC-506 silently logs in when a valid session is stored and /auth/me succeeds', async () =>
  {
    loadTokensMock.mockResolvedValue({ access: 'a1', refresh: 'r1' });
    apiGetMock.mockResolvedValue({ data: { success: true, message: 'ok', ...FAKE_USER } });

    // renderHook() is async in @testing-library/react-native v14.
    const { result } = await renderHook(() => useAutoLogin());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.user).toEqual(FAKE_USER);
    expect(result.current.offline).toBe(false);
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

  it('TC-507 clears tokens when the stored session is genuinely invalid ({success:false})', async () =>
  {
    loadTokensMock.mockResolvedValue({ access: 'stale', refresh: 'stale' });
    apiGetMock.mockResolvedValue({
      data: { success: false, message: 'יש להתחבר מחדש', error: 'unauthorized' },
    });

    const { result } = await renderHook(() => useAutoLogin());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(clearTokensMock).toHaveBeenCalledTimes(1);
    expect(result.current.user).toBeNull();
  });

  // Regression test for improve.md Mobile High #2 / tests.md TC-505: a
  // network-layer failure (no HTTP response at all — the request never
  // reached the server) used to be treated identically to a real invalid
  // session by the hook's single unconditional `catch { clearTokens() }`,
  // wiping a perfectly valid refresh token just because the device was
  // briefly offline at boot. The always-200 contract fixes this as a
  // natural consequence: a genuinely invalid session now resolves normally
  // as {success:false} (asserted above), while only a true network failure
  // still makes axios reject — so the catch block can safely mean "we
  // couldn't reach the server" without also covering "the session is bad."
  it('TC-505 does not clear tokens on a pure network failure (no response from server)', async () =>
  {
    loadTokensMock.mockResolvedValue({ access: 'a1', refresh: 'r1' });
    const networkError = Object.assign(new Error('Network Error'), { request: {} });
    apiGetMock.mockRejectedValue(networkError);

    const { result } = await renderHook(() => useAutoLogin());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(clearTokensMock).not.toHaveBeenCalled();
    expect(result.current.offline).toBe(true);
  });
});
