export interface AuthTokens
{
    access_token:  string;
    refresh_token: string;
}

export interface AuthUser
{
    user_id:  string;
    email:    string;
    username: string;
    is_admin: number;
}
