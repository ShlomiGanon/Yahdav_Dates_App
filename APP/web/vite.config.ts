import { defineConfig } from 'vite';
import react        from '@vitejs/plugin-react';
import tailwindcss  from '@tailwindcss/vite';

export default defineConfig(
{
    plugins:
    [
        tailwindcss(),
        react(),
    ],
    resolve:
    {
        alias:
        {
            '@':       `${import.meta.dirname}/src`,
            '@shared': `${import.meta.dirname}/../shared`,
        },
    },
    server:
    {
        port: 5174,
    },
});
