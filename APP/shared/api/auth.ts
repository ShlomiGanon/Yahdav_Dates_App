import type { AxiosInstance } from 'axios';
import type { AuthTokens, AuthUser } from '../types/auth';

export function createAuthApi(client: AxiosInstance)
{
    return {
        signup(
            email:    string,
            username: string,
            password: string,
        ): Promise<AuthTokens & { user_id: string }>
        {
            return client
                .post('/auth/signup', { email, username, password })
                .then((r) => r.data);
        },

        login(identifier: string, password: string): Promise<AuthTokens>
        {
            return client
                .post('/auth/login', { identifier, password })
                .then((r) => r.data);
        },

        refresh(refresh_token: string): Promise<AuthTokens>
        {
            return client
                .post('/auth/refresh', { refresh_token })
                .then((r) => r.data);
        },

        logout(refresh_token: string): Promise<void>
        {
            return client
                .post('/auth/logout', { refresh_token })
                .then(() => undefined);
        },

        me(): Promise<AuthUser>
        {
            return client.get('/auth/me').then((r) => r.data);
        },
    };
}
