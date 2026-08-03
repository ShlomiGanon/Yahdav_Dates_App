/** @type {import('jest').Config} */
module.exports = {
  preset:          'ts-jest',
  testEnvironment: 'node',
  roots:           ['<rootDir>/tests'],
  setupFiles:      ['<rootDir>/tests/env.ts'],
  testTimeout:     15_000,
  verbose:         true,
};
