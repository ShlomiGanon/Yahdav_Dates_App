import { defineConfig } from 'vite';
import type { Plugin } from 'vite';
import react        from '@vitejs/plugin-react';
import tailwindcss  from '@tailwindcss/vite';
import { APP_NAME } from '../shared/config.ts';

// Replaces the %APP_NAME% placeholder in index.html's <title> with the
// shared constant at build/dev-serve time — keeps the HTML file itself
// free of a hardcoded app name, matching every other consumer (see
// APP/shared/config.ts).
function injectAppName(): Plugin
{
    return {
        name: 'inject-app-name',
        transformIndexHtml(html)
        {
            return html.replace(/%APP_NAME%/g, APP_NAME);
        },
    };
}

export default defineConfig(
{
    plugins:
    [
        tailwindcss(),
        react(),
        injectAppName(),
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
