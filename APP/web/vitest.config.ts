import { defineConfig } from 'vitest/config';

export default defineConfig(
{
    resolve:
    {
        alias:
        {
            '@':       `${import.meta.dirname}/src`,
            '@shared': `${import.meta.dirname}/../shared`,
            // Test files live outside this package, so a bare import of a
            // test-only devDependency needs an explicit alias — Vite's
            // resolver walks up node_modules from the importing file's own
            // directory (APP/tests/web), which never reaches this package's
            // node_modules.
            'axios-mock-adapter': `${import.meta.dirname}/node_modules/axios-mock-adapter`,
        },
    },
    // Test files live outside this package (APP/tests/web), so Vite's dev
    // server needs an explicit allow-list entry — by default it refuses to
    // serve files outside the project root.
    server:
    {
        fs:
        {
            allow: [`${import.meta.dirname}/..`],
        },
    },
    test:
    {
        environment: 'jsdom',
        include: ['../tests/web/**/*.test.ts'],
        globals: false,
    },
});
