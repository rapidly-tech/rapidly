# Rapidly Backoffice

The Rapidly admin dashboard — an internal web-based backoffice for managing the platform's payment infrastructure, file sharing, and organization administration.

## Architecture

It consists of a [FastAPI app](__init__.py) that's mounted on the main Rapidly API.

Endpoints render server-side HTML pages using [Tagflow](https://github.com/lessrest/tagflow), a Python library that uses context managers for composing HTML documents.

The UI layer is built with:

- **[Tailwind 4](https://tailwindcss.com)** and **[DaisyUI 5](https://daisyui.com)** for styling and pre-built components
- **[HTMX](https://htmx.org)** for dynamic content loading without full page reloads
- **[Hyperscript](https://hyperscript.org)** for lightweight inline client-side scripting

This HTMX + DaisyUI approach keeps the backoffice lightweight and server-driven, avoiding the need for a separate SPA frontend.

## Development

Since it's bundled in the Rapidly API, you can run the backoffice with:

```bash
uv run task api
```

This starts the API and the backoffice on the same port, available at [http://127.0.0.1:8000/backoffice](http://127.0.0.1:8000/backoffice).

When adding new styles or components, rebuild the assets bundle so Tailwind and DaisyUI can detect new utility classes:

```bash
uv run task backoffice
```
