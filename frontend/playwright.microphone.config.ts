import {defineConfig} from '@playwright/test';
export default defineConfig({
 outputDir:'../.local/microphone-test-results',
 testDir:'./e2e',testMatch:['microphone.spec.ts','reset.spec.ts'],workers:1,
 use:{baseURL:'http://127.0.0.1:5187',headless:true,channel:'msedge'},
 webServer:{command:'npm run dev -- --port 5187 --strictPort',url:'http://127.0.0.1:5187',reuseExistingServer:false},
});
