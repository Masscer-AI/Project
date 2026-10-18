# Development Conventions

## Code style

These apply to new code. Older code doesn't always follow them yet.

- Don't write comments or docstrings. Name things so the code explains itself. Add a comment only when the code does something surprising that a reader would otherwise "fix".
- Write acronyms in one case: `fileShareDownloadURL`, `API_URL`, `MCPClient`, `WSNumber`.
- Put private helper functions at the top of the file, above the code that uses them.
- Don't add defensive code for cases that can't happen. Check input where it enters the system (API views, tool parameters), then trust it.
- Match the surrounding code: its naming, structure, and how it solves similar problems.
- Manage Python packages with uv (`uv add --project server <package>`), never pip.

## User-facing text

Every string a person reads must sound natural and be perfectly written in its language. That means correct spelling, grammar, punctuation, and accents. For example, write "El proceso terminó", never "El proceso termino".

This covers UI labels, locale files, emails, PDFs, WhatsApp templates, empty states, errors, and buttons.

In the frontend, every string goes through `t()` with a key in both locale files:

- `streaming/client/src/locales/en.json`
- `streaming/client/src/locales/es.json`

Keys use `kebab-case` (e.g. `confirm-remove-member-description`). Use `{{variable}}` for values filled in at runtime.

## Migrations

- The developer runs migrations with `./taskfile.sh migrate`, which runs `makemigrations` and then `migrate`.
- Never run `makemigrations` or `migrate` yourself, and never write schema migration files by hand.
- After changing a model, stop and tell the developer which migration is needed.
- A data migration (moving or fixing existing rows) is the one exception you may write by hand, and only after the developer agrees.

## Feature flags

- All flags live in `KNOWN_FEATURE_FLAGS` in `server/api/authenticate/feature_flags_registry.py`. `sync_system_data` copies them to the database.
- Organization owners get every flag in the registry automatically.
- Each flag needs two translation keys in both locale files: `ff-<flag-name>` (display name) and `ff-<flag-name>-desc` (tooltip).

## Adding an AI tool

A tool must be registered in every place below. Miss one and it quietly disappears from that surface.

1. Create `server/api/ai_layers/tools/<name>.py` with a Pydantic parameters model and `get_tool(**context)`. `get_tool` returns `name`, `description`, `parameters`, and `function`.
2. Add it to `TOOL_REGISTRY` in `server/api/ai_layers/tools/__init__.py`.
3. Add it to `USER_REQUIRED_TOOL_NAMES` in the same file if it needs a signed-in user.
4. Add it to one `MCP_*_TOOL_NAMES` group in `server/api/ai_layers/mcp_access.py`. These groups fill the agent tool picker.
5. Add `widget-capability-<name>-title` and `widget-capability-<name>-description` to both locale files.
6. Add it to `WHATSAPP_CAPABILITY_NAMES` in `streaming/client/src/routes/whatsapp/shared.ts` if WhatsApp lines may use it.

Then restart the Celery worker so it loads the tool (see `testing.md`).

## Adding a page

- Add the React route in `streaming/client/src/main.tsx`.
- Paths with more than one segment (like `/d/<id>`) also need a handler in `streaming/server/routes.py` that returns `index.html`. One-segment paths are already covered by `/{page_name}`.
- Build new UI with Mantine components and Tabler icons. Mantine's own styles override Tailwind layout classes such as `flex` on Mantine components, so use `Group` and `Stack` for layout.
- Run `./taskfile.sh front` after any frontend change.

## WhatsApp templates

- Templates live in `server/api/whatsapp/template_registry.py`. The header, body, footer, and buttons must match the Meta-approved text exactly.
- Get the template approved in Meta first, then add its definition, then sync it to the database with the `sync_whatsapp_templates` command or the "Sync default templates" admin action.
- Meta may move a template to another category, for example from Utility to Marketing. Set `category` to whatever Meta shows.
- Meta allows editing an approved template once every 24 hours, and at most 10 times in 30 days. A template's name and language can't change, so create a new template instead.

## Environment settings

A new environment variable also needs Pulumi config: `pulumi/modules/config.ts`, plus `pulumi/modules/parameter-store.ts` for secrets. Never commit secrets.
