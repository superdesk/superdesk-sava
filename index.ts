// Root Angular module for superdesk-sava.
//
// External TypeScript packages are registered as Superdesk "apps" in the host's
// client/superdesk.config.js. That registration does two things:
//   1. whitelists this package for the host webpack's ts-loader (so our .ts/.tsx
//      is transpiled instead of being parsed as plain JS), and
//   2. makes the host import `require("superdesk-sava").default.name` and add it
//      as an Angular module dependency of the main app.
//
// All actual SAVA UI is contributed by client/sava-extension (loaded separately
// via the host's index.ts as a superdesk-core extension), so this root module is
// intentionally empty — it exists only to satisfy the "app" contract above.

declare const angular: any;

// The module name MUST match the package name used in the host's
// superdesk.config.js `apps` list ("superdesk-sava"). Superdesk adds that
// string directly as an Angular module dependency, so a mismatch throws
// "[$injector:nomod] Module 'superdesk-sava' is not available".
export default angular.module('superdesk-sava', []);
