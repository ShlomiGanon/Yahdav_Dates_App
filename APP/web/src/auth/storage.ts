export const webTokenStorage =
{
    getAccessToken(): string | null
    {
        return sessionStorage.getItem('access_token');
    },

    setAccessToken(token: string | null): void
    {
        if (token)
        {
            sessionStorage.setItem('access_token', token);
        }
        else
        {
            sessionStorage.removeItem('access_token');
        }
    },

    getRefreshToken(): string | null
    {
        return localStorage.getItem('refresh_token');
    },

    setRefreshToken(token: string | null): void
    {
        if (token)
        {
            localStorage.setItem('refresh_token', token);
        }
        else
        {
            localStorage.removeItem('refresh_token');
        }
    },

    clear(): void
    {
        sessionStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
    },
};
