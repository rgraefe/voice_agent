import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./e2e',use:{baseURL:process.env.TEST_BASE_URL||'http://localhost:8000',headless:true,channel:'msedge'},workers:1,reporter:'list'});

