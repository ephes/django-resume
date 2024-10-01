import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',  // Set the environment to jsdom
    globals: true,
  },
});
