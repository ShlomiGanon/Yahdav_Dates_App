import { api } from './axios';
import type { ApiEnvelope, UserDetail, UserListResponse, UserStatus, UserSummary } from '../types';

export const usersApi = {
  list: (params: { limit: number; offset: number; search?: string }) =>
    api.get<ApiEnvelope & UserListResponse>('/api/admin/users', { params }).then((r) => r.data),

  get: (id: string) =>
    api.get<ApiEnvelope & UserDetail>(`/api/admin/users/${id}`).then((r) => r.data),

  updateStatus: (id: string, status: UserStatus) =>
    api
      .put<ApiEnvelope & UserSummary>(`/api/admin/users/${id}/status`, { status })
      .then((r) => r.data),

  delete: (id: string) =>
    api.delete<ApiEnvelope>(`/api/admin/users/${id}`).then((r) => r.data),
};
