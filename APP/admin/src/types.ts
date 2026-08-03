export interface AdminUser {
  user_id: string;
  email: string;
  username: string;
  is_admin: boolean;
}

export type UserStatus = 'active' | 'suspended' | 'banned';

export interface UserSummary {
  user_id: string;
  name: string;
  city: string;
  gender: string;
  photo_url: string | null;
  status: UserStatus;
  registered_at: string;
  username: string | null;
  email: string | null;
  is_admin: boolean;
}

export interface UserDetail extends UserSummary {
  bio: string;
  date_of_birth: string;
  region: string;
  updated_at: string;
  last_login_at: string | null;
}

export interface UserListResponse {
  total: number;
  users: UserSummary[];
}
