import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    alias: {
      '@': `${import.meta.dirname}/src`,
      '@shared': `${import.meta.dirname}/../shared`,
      // Test files live outside this package (APP/tests/admin), so a bare
      // import of a test-only devDependency needs an explicit alias — see
      // the matching note in APP/web/vitest.config.ts for why.
      'axios-mock-adapter': `${import.meta.dirname}/node_modules/axios-mock-adapter`,
      '@testing-library/react': `${import.meta.dirname}/node_modules/@testing-library/react`,
      react: `${import.meta.dirname}/node_modules/react`,
    },
  },
  // Test files live outside this package — Vite's dev server otherwise
  // refuses to serve files outside the project root.
  server: {
    fs: {
      allow: [`${import.meta.dirname}/..`],
    },
  },
  test: {
    environment: 'jsdom',
    include: ['../tests/admin/**/*.test.ts'],
    globals: false,
  },
});
