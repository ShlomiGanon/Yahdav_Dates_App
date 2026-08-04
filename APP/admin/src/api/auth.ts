import { api } from './axios';
import type { AdminUser, ApiEnvelope } from '../types';

interface LoginResponse extends ApiEnvelope {
  user_id: string;
  email: string;
  username: string;
  is_admin: boolean;
  access_token: string;
  refresh_token: string;
}

export const authApi = {
  login: (identifier: string, password: string) =>
    api.post<LoginResponse>('/auth/login', { identifier, password }).then((r) => r.data),

  refresh: (refreshToken: string) =>
    api.post<LoginResponse>('/auth/refresh', { refresh_token: refreshToken }).then((r) => r.data),

  me: () =>
    api.get<ApiEnvelope & AdminUser>('/auth/me').then((r) => r.data),

  logout: (refreshToken: string) =>
    api.post<ApiEnvelope>('/auth/logout', { refresh_token: refreshToken }).then((r) => r.data),
};
