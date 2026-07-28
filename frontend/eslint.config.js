import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";

export default [
  { ignores: ["dist", "node_modules"] },
  js.configs.recommended,
  {
    // Node-context config files (run by Vite/Node, not the browser).
    files: ["*.config.js", "vite.config.js"],
    languageOptions: {
      globals: { __dirname: "readonly", process: "readonly" },
    },
  },
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: {
        window: "readonly",
        document: "readonly",
        fetch: "readonly",
        console: "readonly",
        URLSearchParams: "readonly",
        sessionStorage: "readonly",
        AbortController: "readonly",
        PopStateEvent: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
      },
    },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Existing effects intentionally reset pagination/loading when inputs change.
      "react-hooks/set-state-in-effect": "off",
    },
  },
];
