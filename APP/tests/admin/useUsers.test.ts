vi.mock('../../admin/src/api/users', () => ({
    usersApi: { list: vi.fn() },
}));

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { usersApi } from '../../admin/src/api/users';
import { useUsers } from '../../admin/src/sections/users/hooks/useUsers';

const listMock = usersApi.list as unknown as ReturnType<typeof vi.fn>;

function page(n: number, total = 100): { users: unknown[]; total: number }
{
    return { users: Array.from({ length: n }, (_, i) => ({ user_id: `${i}` })), total };
}

beforeEach(() =>
{
    listMock.mockReset();
    listMock.mockResolvedValue(page(20));
});

describe('useUsers', () =>
{
    it('fetches page 1 on mount with the default page size', async () =>
    {
        const { result } = renderHook(() => useUsers());

        await waitFor(() => expect(result.current.loading).toBe(false));

        expect(listMock).toHaveBeenCalledWith({ limit: 20, offset: 0 });
        expect(result.current.users.length).toBe(20);
        expect(result.current.total).toBe(100);
        expect(result.current.totalPages).toBe(5);
    });

    it('setSearch resets to page 1 and includes the search param', async () =>
    {
        const { result } = renderHook(() => useUsers());
        await waitFor(() => expect(result.current.loading).toBe(false));

        act(() => result.current.setPage(3));
        await waitFor(() => expect(result.current.page).toBe(3));

        act(() => result.current.setSearch('alice'));

        await waitFor(() => expect(result.current.page).toBe(1));
        await waitFor(() =>
            expect(listMock).toHaveBeenLastCalledWith({ limit: 20, offset: 0, search: 'alice' }),
        );
    });

    it('setPage clamps below 1 up to 1', async () =>
    {
        const { result } = renderHook(() => useUsers());
        await waitFor(() => expect(result.current.loading).toBe(false));

        act(() => result.current.setPage(-5));

        await waitFor(() => expect(result.current.page).toBe(1));
    });

    it('setPage clamps above totalPages down to totalPages', async () =>
    {
        listMock.mockResolvedValue(page(20, 40)); // 40 users / 20 per page = 2 pages
        const { result } = renderHook(() => useUsers());
        await waitFor(() => expect(result.current.totalPages).toBe(2));

        act(() => result.current.setPage(99));

        await waitFor(() => expect(result.current.page).toBe(2));
    });

    it('surfaces a Hebrew error message and stops loading when the request fails', async () =>
    {
        listMock.mockReset();
        listMock.mockRejectedValue(new Error('network down'));

        const { result } = renderHook(() => useUsers());

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.error).toBe('שגיאה בטעינת המשתמשים');
    });

    it('refresh() re-fetches the current page and search without changing them', async () =>
    {
        const { result } = renderHook(() => useUsers());
        await waitFor(() => expect(result.current.loading).toBe(false));

        listMock.mockClear();
        act(() => result.current.refresh());

        await waitFor(() => expect(listMock).toHaveBeenCalledTimes(1));
        expect(result.current.page).toBe(1);
    });
});
