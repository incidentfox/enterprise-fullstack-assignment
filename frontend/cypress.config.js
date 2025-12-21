// Keep this file dependency-free so CI can run Cypress via `npx cypress@...`
// without needing `cypress` installed in the repo's node_modules.
module.exports = {
  e2e: {
    baseUrl: process.env.CYPRESS_BASE_URL || "http://localhost:3000",
    supportFile: false,
    video: false,
    screenshotOnRunFailure: true,
  },
};


