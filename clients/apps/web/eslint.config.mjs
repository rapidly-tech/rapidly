import { nextJsConfig } from '@rapidly-tech/eslint-config/next-js'

/** @type {import("eslint").Linter.Config} */
export default [
  ...nextJsConfig,
  {
    rules: {
      // TypeScript handles these — disable redundant JS/React checks
      'react/prop-types': 'off',
      'react/display-name': 'off',
      'no-undef': 'off',
      'no-redeclare': 'off',

      // Allow @ts-nocheck/@ts-ignore — many files legitimately use them
      '@typescript-eslint/ban-ts-comment': 'off',

      // Warn on explicit any to catch regressions
      '@typescript-eslint/no-explicit-any': 'warn',

      // Allow aliasing this
      '@typescript-eslint/no-this-alias': 'off',

      // Allow empty object types (used for extending interfaces)
      '@typescript-eslint/no-empty-object-type': 'off',

      // Allow short-circuit and ternary expressions
      '@typescript-eslint/no-unused-expressions': [
        'warn',
        {
          allowShortCircuit: true,
          allowTernary: true,
          allowTaggedTemplates: true,
        },
      ],

      // Allow underscore-prefixed unused variables (common pattern for destructuring)
      '@typescript-eslint/no-unused-vars': [
        'warn',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
          destructuredArrayIgnorePattern: '^_',
          ignoreRestSiblings: true,
        },
      ],

      // React Compiler rules — off by default; enable selectively when
      // auditing performance (these are informational, not bugs)
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/refs': 'off',
      'react-hooks/static-components': 'off',
      'react-hooks/preserve-manual-memoization': 'off',
      'react-hooks/immutability': 'off',
      'react-hooks/purity': 'off',
      'react-hooks/incompatible-library': 'off',
    },
  },
  {
    files: ['**/*.tsx'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: 'JSXOpeningElement[name.name="img"]',
          message:
            'Use <UploadImage /> from @/components/Image/Image or <StaticImage /> from @/components/Image/StaticImage instead of <img>.',
        },
      ],
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: 'next/image',
              message:
                'Use <StaticImage /> from @/components/Image/StaticImage instead of next/image.',
            },
          ],
        },
      ],
    },
  },
  {
    // Third-party WebGL library — suppress expression warnings
    files: ['**/GradientMesh.js'],
    rules: {
      '@typescript-eslint/no-unused-expressions': 'off',
      'no-empty': 'off',
    },
  },
  {
    ignores: [
      'node_modules/**',
      '.next/**',
      'out/**',
      'build/**',
      'next-env.d.ts',
      'e2e/**',
    ],
  },
]
