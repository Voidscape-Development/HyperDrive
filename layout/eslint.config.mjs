// Lints the layouts' own scripts (not the vendored libraries). Pages are
// classic scripts sharing one global scope per page, so the runtime's and
// libraries' globals are declared here.
import js from "@eslint/js";

const browser = Object.fromEntries(
  [
    "window",
    "document",
    "location",
    "console",
    "setTimeout",
    "clearTimeout",
    "setInterval",
    "clearInterval",
    "requestAnimationFrame",
    "fetch",
    "URL",
    "URLSearchParams",
    "Image",
    "CustomEvent",
    "ResizeObserver",
    "MutationObserver",
    "CSS",
    "localStorage",
    "getComputedStyle",
    "performance",
    "navigator",
    "HTMLElement",
  ].map((name) => [name, "readonly"]),
);

export default [
  {
    ignores: ["**/*.min.js", "**/leaflet/**", "**/proj*.js", "eslint.config.mjs"],
  },
  js.configs.recommended,
  {
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        ...browser,
        HD: "readonly",
        VS: "readonly",
        HDBracket: "readonly",
        TB: "readonly",
        CS: "readonly",
        $: "readonly",
        jQuery: "readonly",
        _: "readonly",
        gsap: "readonly",
        ColorThief: "readonly",
        io: "readonly",
        L: "readonly",
      },
    },
    rules: {
      // HD, VS... are both defined by a script and listed above
      "no-redeclare": ["error", { builtinGlobals: false }],
      // Layout scripts define what the page's inline scripts and other
      // includes use
      "no-unused-vars": ["error", { vars: "local", args: "none", caughtErrors: "none" }],
    },
  },
];
