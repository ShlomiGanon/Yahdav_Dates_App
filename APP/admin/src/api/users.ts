import { api } from './axios';
import type { UserDetail, UserListResponse, UserStatus, UserSummary } from '../types';

export const usersApi = {
  list: (params: { limit: number; offset: number; search?: string }) =>
    api.get<UserListResponse>('/admin/users', { params }).then((r) => r.data),

  get: (id: string) =>
    api.get<UserDetail>(`/admin/users/${id}`).then((r) => r.data),

  updateStatus: (id: string, status: UserStatus) =>
    api
      .put<UserSummary>(`/admin/users/${id}/status`, { status })
      .then((r) => r.data),

  delete: (id: string) =>
    api.delete(`/admin/users/${id}`),
};
