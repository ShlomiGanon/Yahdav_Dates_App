import type { AxiosInstance } from 'axios';
import type { AuthTokens, AuthUser } from '../types/auth';
import type { ApiEnvelope } from '../types/api';

export function createAuthApi(client: AxiosInstance)
{
    return {
        signup(
            email:    string,
            username: string,
            password: string,
        ): Promise<ApiEnvelope & AuthUser>
        {
            return client
                .post('/api/auth/signup', { email, username, password })
                .then((r) => r.data);
        },

        login(identifier: string, password: string): Promise<ApiEnvelope & AuthTokens & AuthUser>
        {
            return client
                .post('/api/auth/login', { identifier, password })
                .then((r) => r.data);
        },

        refresh(refresh_token: string): Promise<ApiEnvelope & AuthTokens & AuthUser>
        {
            return client
                .post('/api/auth/refresh', { refresh_token })
                .then((r) => r.data);
        },

        logout(refresh_token: string): Promise<ApiEnvelope>
        {
            return client
                .post('/api/auth/logout', { refresh_token })
                .then((r) => r.data);
        },

        me(): Promise<ApiEnvelope & AuthUser>
        {
            return client.get('/api/auth/me').then((r) => r.data);
        },
    };
}
