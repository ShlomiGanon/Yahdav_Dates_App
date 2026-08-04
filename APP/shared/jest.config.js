/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: 'node',
  roots: ['<rootDir>/../tests/shared'],
  testTimeout: 10_000,
  verbose: true,
  passWithNoTests: true,
  modulePaths: ['<rootDir>/node_modules'],
  transform: {
    '^.+\\.tsx?$': ['ts-jest', { tsconfig: '<rootDir>/../tests/shared/tsconfig.json' }],
  },
};
