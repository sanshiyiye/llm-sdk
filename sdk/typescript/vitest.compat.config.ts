import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    root: '.',
    include: ['../compat-tests/typescript-sdk.test.ts'],
    environment: 'node',
  },
})
