# MCP Server for Masscer Agents

Expose Masscer conversational agents as MCP tools over Streamable HTTP at `/mcp`.

## Architecture

- **Protocol server**: FastAPI streaming service (`streaming/server/mcp/`) — MCP SDK Streamable HTTP
- **Gateway API**: Django (`/v1/ai_layers/mcp/*`) — auth, agent dispatch, Celery result polling
- **Execution**: `conversation_agent_task` → `AgentLoop` (production path)

## Setup (Claude / ChatGPT — OAuth)

Masscer is an OAuth 2.1 authorization server for remote MCP clients.

1. **Integrations → OAuth MCP clients** — register a client with redirect URIs:
   - Claude: `https://claude.ai/api/mcp/auth_callback`
   - ChatGPT: `https://chatgpt.com/connector/oauth/{connector-id}` (per connector)
2. In the MCP client: **Add custom connector** → URL: `https://your-app.example.com/mcp` (no trailing slash)
3. **Advanced OAuth settings** (optional): paste Masscer **Client ID** and **Client Secret** from step 1.  
   Claude/ChatGPT can also use **Dynamic Client Registration** or **CIMD** without manual credentials.
4. Complete the browser consent flow (login → pick agents/tools → Allow).

Discovery endpoints (public HTTPS):

| Endpoint | Description |
|----------|-------------|
| `/.well-known/oauth-protected-resource` | Resource metadata (FastAPI) |
| `/.well-known/oauth-authorization-server` | Authorization server metadata (Django) |
| `/oauth/authorize` | Authorization Code + PKCE |
| `/oauth/token` | Token endpoint (form-urlencoded) |
| `/oauth/register` | Dynamic Client Registration (RFC 7591) |

## Setup (Cursor — static Bearer)

1. Create an MCP credential in **Integrations → Masscer MCP**
2. Copy the Cursor config into `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "masscer-My Agent": {
      "url": "https://your-app.example.com/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_KEY"
      }
    }
  }
}
```

3. Restart Cursor or reload MCP servers

## Setup (Claude — legacy static Bearer, beta)

Some Claude plans support **Request headers** instead of OAuth: use `Authorization: Bearer YOUR_MCP_KEY` from Integrations.

## MCP tools

| Tool | Description |
|------|-------------|
| `ask_<agent_slug>` | Run a Masscer conversational agent |
| `download_attachment` | Fetch a file by `attachment_id` from a prior agent result |

### Downloading attachments

Agent tools return JSON with an `attachments` array. Each item includes:

- `attachment_id`, `type`, `name`, …
- `download_url` — absolute public URL (`FRONTEND_URL`) with a **signed token** (~1 hour `expires_at`)
- `expires_at` — ISO timestamp when the signed URL stops working

Clients that support MCP media blocks can also call **`download_attachment`**:

1. `call_tool ask_my_agent` → response includes `attachments[].attachment_id` (+ `download_url`)
2. Open `download_url` in a browser / HTTP client (no Bearer needed), **or**
3. `call_tool download_attachment` with `{ "attachment_id": "..." }` → `AudioContent` / `ImageContent` / `EmbeddedResource`

Note: Claude Desktop / ChatGPT often cannot render MCP `AudioContent` / images inline.
The signed `download_url` is the fallback so users can still fetch the file.

## API (Django gateway)

Gateway accepts `Authorization: Bearer <MCPClient.key>` **or** OAuth access tokens.


| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/ai_layers/mcp/agents/` | GET | List agents as tool metadata |
| `/v1/ai_layers/mcp/run/` | POST | Dispatch agent task |
| `/v1/ai_layers/mcp/result/<task_id>/` | GET | Poll Celery result |
| `/v1/ai_layers/mcp/attachments/<attachment_id>/` | GET | Download attachment (Bearer auth) |

Credential management (user login token):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/ai_layers/mcp/credentials/` | GET/POST | List / create credentials |
| `/v1/ai_layers/mcp/credentials/<id>/` | DELETE | Revoke credential |
| `/v1/ai_layers/mcp/connection-config/?credential_id=` | GET | Fetch Cursor config |

## curl examples

```bash
# List tools (via Django gateway)
curl -s -H "Authorization: Bearer $MCP_KEY" \
  https://app.example.com/v1/ai_layers/mcp/agents/

# Run agent
curl -s -X POST -H "Authorization: Bearer $MCP_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_slug":"my-agent","message":"Hello"}' \
  https://app.example.com/v1/ai_layers/mcp/run/

# Poll result
curl -s -H "Authorization: Bearer $MCP_KEY" \
  https://app.example.com/v1/ai_layers/mcp/result/$TASK_ID/
```

## Environment variables

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `API_URL` | FastAPI | `http://localhost:8000` | Django base URL for gateway |
| `MCP_POLL_TIMEOUT_SEC` | FastAPI | `240` | Max wait for agent completion |
| `MCP_POLL_INTERVAL_SEC` | FastAPI | `2` | Poll interval during tool call |
| `MCP_ATTACHMENT_MAX_BYTES` | FastAPI | `10485760` | Max attachment size for `download_attachment` (10MB) |
| `FRONTEND_URL` | Django + FastAPI | — | Public app URL (OAuth issuer + MCP resource id) |
| `INTERNAL_MCP_INTROSPECT_TOKEN` | Django + FastAPI | — | Shared secret for token introspection |
| `MCP_OAUTH_ACCESS_TOKEN_TTL` | Django | `3600` | OAuth access token lifetime (seconds) |
| `MCP_OAUTH_REFRESH_TOKEN_TTL` | Django | `2592000` | OAuth refresh token lifetime (seconds) |
| `MCP_OAUTH_AUTH_CODE_TTL` | Django | `60` | Authorization code lifetime (seconds) |

## Database migration

Run from repo root:

```bash
./migrate
```

This creates the `MCPClient` model and `mcp_oauth` OAuth tables.

## Security notes

- MCP credentials are scoped to the owning user and respect `accessible_agents_qs`
- Optional `allowed_agents` M2M further restricts which agents a credential can invoke
- Revoked credentials and OAuth tokens are rejected immediately
- OAuth uses Authorization Code + PKCE (S256), refresh token rotation, and resource indicators (RFC 8707)
- Unauthenticated `/mcp` requests return HTTP 401 with `WWW-Authenticate` for client discovery
