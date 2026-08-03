import { api } from './axios';
import type { AdminUser } from '../types';

interface LoginResponse {
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

  me: () =>
    api.get<AdminUser>('/auth/me').then((r) => r.data),

  logout: (refreshToken: string) =>
    api.post('/auth/logout', { refresh_token: refreshToken }).catch(() => {}),
};
