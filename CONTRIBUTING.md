# How to Contribute to Rapidly

We appreciate your interest in helping improve Rapidly. This guide outlines the workflow and expectations for all contributors.

## Before You Start

Every contribution (other than trivial fixes) must be tied to a tracked issue. This prevents duplicate work and ensures alignment with the project's direction.

1. Search the [issue tracker](https://github.com/rapidly-tech/rapidly/issues) for an existing issue, or open a new one describing your proposed change.
2. Leave a comment requesting assignment.
3. Wait for a maintainer to assign the issue to you.
4. Begin work only after assignment, then open your pull request.

### Trivial Fixes

The following kinds of changes may be submitted without a prior issue:

- Typo corrections in docs or comments
- Broken link repairs
- Whitespace or formatting fixes
- Documentation version bumps

Anything that touches application logic, dependencies, database schemas, API contracts, configuration, or UI components requires an issue first. When unsure, open an issue -- it is always the safer choice.

## Development Setup

Refer to [`DEVELOPMENT.md`](./DEVELOPMENT.md) for full environment setup instructions. A quick summary:

```bash
# Start infrastructure (PostgreSQL, Redis, Minio)
cd server && docker compose up -d

# Backend API
uv sync && uv run task api        # runs on http://127.0.0.1:8000

# Frontend
cd clients && pnpm install && pnpm dev   # runs on http://127.0.0.1:3000

# Linting & tests
uv run task lint && uv run task lint_types
uv run task test
pnpm lint && pnpm test
```

## Policy on AI-Assisted Contributions

Using AI coding assistants is perfectly fine. What is not acceptable is submitting code you have never executed. Every change must be built, run, and tested in your local environment before you open a pull request. Pull requests that appear to be untested machine output will be closed without review.

## Coding Standards

### General Principles

- Prefer clear, self-documenting code over comments.
- Keep changes scoped to the issue you are working on.
- Follow existing patterns in the codebase -- consistency matters.
- Adhere to SOLID design principles where applicable.

### Backend (Python / FastAPI)

- Run `uv run task lint && uv run task lint_types` before pushing.
- Run `uv run task test` and ensure all tests pass.
- Follow the modular layout under `server/rapidly/`.
- Use async/await correctly throughout.

### Frontend (TypeScript / Next.js)

- Use `pnpm` as the package manager.
- Build on the shared component library in `clients/packages/ui`.
- Style with Tailwind CSS and follow the dark-mode conventions described in the frontend guide.

## Pull Request Review

1. All CI checks (lint, typecheck, tests) must pass.
2. A maintainer will review for code quality, security, performance, and architectural fit.
3. Respond to review feedback in a timely manner.
4. Squash commits if the maintainer requests it.

## Contributions We Welcome

- **Bug fixes** -- reproduce, fix, and add a regression test.
- **New features** -- discuss in an issue first.
- **Documentation** -- improvements to guides, API docs, or inline comments.
- **Test coverage** -- additional unit or integration tests.
- **Tooling** -- developer experience improvements.

## Contributions We Will Decline

- PRs without a linked issue (except trivial fixes).
- Untested or unverified code.
- Changes that break existing functionality.
- Large-scale refactors without prior discussion.
- Submissions that ignore our coding standards.

## License

By submitting a contribution you agree that your work will be licensed under the same terms as the rest of the project.

---

Quality matters more than velocity. Take the time to test thoroughly and write clean code.
