module.exports = {
  testEnvironment: 'node',
  testMatch: ['**/tests/**/*.test.js'],
  setupFiles: ['<rootDir>/tests/setup.js'],
  verbose: true,
  clearMocks: true,
  collectCoverageFrom: [
    'pages/**/*.js',
    'app.js',
    '!**/node_modules/**'
  ]
};
