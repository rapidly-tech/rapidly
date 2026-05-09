# Rapidly Clients

## What's inside?

This [Turborepo](https://turbo.build/) includes the following packages/apps:

### Apps and Packages

- `apps/web`: [rapidly.tech](https://rapidly.tech) – [Next.js](https://nextjs.org/) app
- `packages/ui`: Shared resources
- `packages/client`: Internal API client generated from OpenAPI spec

Each package/app is 100% [TypeScript](https://www.typescriptlang.org/).

### Install

```bash
pnpm install
```

### Build

To build all apps and packages, run the following command:

```bash
pnpm build
```

### Develop

```bash
pnpm dev
```

### Generate API client from OpenAPI spec

```bash
pnpm generate
```
