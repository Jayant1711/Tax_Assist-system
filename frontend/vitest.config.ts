// Sprint 3 Objective E — Vitest unit suite (design §6).
// jsdom + React plugin + globals; setup file registers jest-dom matchers
// on vitest's expect via '@testing-library/jest-dom/vitest'.
// The Playwright E2E specs (Wave G) live in ./e2e and run via
// `npm run test:e2e` — excluded here so each runner owns its own suite.
import { defineConfig, configDefaults } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './vitest.setup.ts',
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
});
