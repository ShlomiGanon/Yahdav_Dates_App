/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: 'node',
  roots: ['<rootDir>/../tests/backend'],
  setupFiles: ['<rootDir>/../tests/backend/env.ts'],
  testTimeout: 15_000,
  verbose: true,
  // Test files live outside this package (APP/tests/backend), so bare
  // package imports ('express', 'supertest', ...) need an explicit
  // absolute lookup path — Node's normal upward node_modules walk from
  // APP/tests/backend would never reach APP/backend/node_modules.
  modulePaths: ['<rootDir>/node_modules'],
  // isolatedModules (set in the tests tsconfig) transpiles each file
  // independently — syntax-only, no cross-package type/program
  // resolution. Type errors in test files won't be caught here —
  // that's an accepted tradeoff for keeping the relocated test folder
  // simple and CI-portable; `npm run build`'s tsc pass still
  // type-checks src/.
  transform: {
    '^.+\\.tsx?$': ['ts-jest', { tsconfig: '<rootDir>/../tests/backend/tsconfig.json' }],
  },
};
