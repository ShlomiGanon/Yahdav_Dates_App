/** @type {import('jest').Config} */
module.exports = {
  preset: 'jest-expo',
  roots: ['<rootDir>/../tests/mobile'],
  // Test files live outside this package (APP/tests/mobile) — see
  // APP/backend/jest.config.js for the same pattern and why it's needed.
  modulePaths: ['<rootDir>/node_modules'],
};
