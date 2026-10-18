# End-to-End Testing

How to check a change in the running dev app, not just in unit tests.

The dev environment runs in Docker and is reachable at `https://app.charlytoc.dev`. Nginx serves the app and the Django API (`/v1/...`) on that same domain.

## Containers and reloading

| Container | What it runs | Picks up code changes |
| --- | --- | --- |
| `masscer-django` | Django API | Yes, auto-reloads |
| `masscer-fastapi` | Page server, sockets, MCP (`streaming/main.py`) | Yes, uvicorn `reload=True` |
| `masscer-celery-worker` | Agent runs, tools, background tasks | **No**, restart it |
| `masscer-celery-beat` | Scheduled tasks | No, restart it |

After changing tools, tasks, or anything the worker imports:

```bash
docker restart masscer-celery-worker
```

If you skip this, the worker logs `Skipping unknown tool '<name>'` and the agent runs without the tool.

## Frontend

FastAPI serves the built bundle from `streaming/client/dist`. Rebuild after frontend changes:

```bash
./taskfile.sh front
```

A new multi-segment page route (like `/d/<id>`) also needs a handler in `streaming/server/routes.py` that returns `index.html`. Without one, the route returns 404 even though React Router knows it.

`npx tsc` from `streaming/` checks nothing, because `tsconfig.json` includes `src` and the code lives in `client/src`. To type-check, use a temporary config that extends it with `"include": ["<repo>/streaming/client/src"]`. The client already has many type errors, so filter the output to the files you changed.

## Backend tests

```bash
./taskfile.sh test api.messaging.tests_file_shares --keepdb
```

Some suites already fail on `master`. Before blaming your change, run the same suites with your changes stashed and compare.

Tests for new models need their migration first. Per `conventions.md`, the developer runs migrations, so ask them to.

## Data and accounts

Run Django code inside the running app:

```bash
docker exec masscer-django python manage.py shell -c "<python>"
```

Use it to create test conversations and attachments, or to call a tool's `_impl` function directly. Don't use the user's real files. Create your own test data, then remove it or tell the user it's there.

Ask the user for login details, or create a test user. Never write credentials into the repo.

## Calling the API as a user

```bash
curl -s -X POST https://app.charlytoc.dev/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"<email>","password":"<password>"}'
```

The response has a `token`. Send it as `Authorization: Token <token>`.

List the user's agents with `GET /v1/ai_layers/agents/`.

## Running an agent

```bash
curl -s -X POST https://app.charlytoc.dev/v1/ai_layers/agent-task/conversation/ \
  -H "Authorization: Token $TOKEN" -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "<uuid>",
    "agent_slugs": ["<agent-slug>"],
    "tool_names": ["list_attachments", "create_file_share"],
    "user_inputs": [{"type": "input_text", "text": "<prompt>"}]
  }'
```

`tool_names` in the request replaces the agent's saved tools for that run, so you can test a tool the agent doesn't have turned on.

Poll until `"active": false`:

```bash
curl -s "https://app.charlytoc.dev/v1/ai_layers/agent-task/status/?conversation_id=<uuid>" \
  -H "Authorization: Token $TOKEN"
```

Then read the reply from the conversation's messages, using the Django shell or the conversation endpoint. Check which tools ran:

```bash
docker logs masscer-celery-worker --since 5m 2>&1 \
  | grep -E "Resolved tool|Tool .* completed|Skipping unknown tool|Traceback"
```

Don't let a test send WhatsApp messages or emails to real people without asking the user first.

## Checking pages

There is no interactive browser. Use headless Chrome for screenshots, then open the PNG to look at it:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --user-data-dir=<tmp-dir> --window-size=1280,800 --virtual-time-budget=8000 \
  --screenshot=<out.png> "https://app.charlytoc.dev/<path>"
```

- `--dump-dom` instead of `--screenshot` prints the rendered HTML, which is useful for checking links.
- `--lang=es --accept-lang=es` renders the Spanish version.
- Headless Chrome lays out pages at least 500px wide. A narrower `--window-size` crops the page instead of showing a phone layout, so use 600px to check small screens.

## Known Gaps

- Headless Chrome can't click, type, or log in through the UI. Test flows behind a login through the API, and use screenshots for public pages.
- There is no true phone-width check below 500px.
- The frontend has no working `tsc` setup from the repo root.
- Some backend suites fail on `master` (for example, "No LanguageModel records exist" in `api.ai_layers.tests`).
