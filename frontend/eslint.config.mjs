import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  // Task 5 bounds:
  // - app/** chỉ import qua @/features/<module> index (cấm @/lib, @/components).
  // - features/** cấm import sâu @/features/*/*, cấm leo ../, cấm @/lib/@/components.
  //   Intra-feature dùng ./ (flat), cross-feature qua @/features/<module> index.
  {
    files: ["app/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/lib/**", "@/components/**"],
              message: "Dời vào frontend/features/<module>, import qua @/features/<module> index.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["features/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/lib/**", "@/components/**"],
              message: "Dời vào frontend/features/<module>, import qua @/features/<module> index.",
            },
            {
              group: ["@/features/*/*", "./*/*"],
              message: "Cấm import sâu features/*/*. Intra-feature dùng ./, cross-feature qua @/features/<module> index.",
            },
          ],
        },
      ],
    },
  },
]);

export default eslintConfig;
