# MCP Server for Masscer Agents

Expose Masscer conversational agents as MCP tools over Streamable HTTP at `/mcp`.

## Architecture

- **Protocol server**: FastAPI streaming service (`streaming/server/mcp/`) — MCP SDK Streamable HTTP
- **Gateway API**: Django (`/v1/ai_layers/mcp/*`) — auth, agent dispatch, Celery result polling
- **Execution**: `conversation_agent_task` → `AgentLoop` (production path)

## Setup (Cursor)

1. Open an agent in **Configure** → **MCP Connection**
2. Create a credential (optionally limit to that agent)
3. Copy the Cursor config into `~/.cursor/mcp.json`:

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

4. Restart Cursor or reload MCP servers

## Setup (Claude)

1. Create an MCP credential in Masscer (same as above)
2. Claude: **Settings → Connectors → Add custom connector**
3. URL: `https://your-app.example.com/mcp`
4. Use Bearer token authentication when prompted

## API (Django gateway)

All MCP gateway endpoints require `Authorization: Bearer <MCPClient.key>`.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/ai_layers/mcp/agents/` | GET | List agents as tool metadata |
| `/v1/ai_layers/mcp/run/` | POST | Dispatch agent task |
| `/v1/ai_layers/mcp/result/<task_id>/` | GET | Poll Celery result |

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

## Database migration

Run from repo root:

```bash
./migrate
```

This creates the `MCPClient` model.

## Security notes

- MCP credentials are scoped to the owning user and respect `accessible_agents_qs`
- Optional `allowed_agents` M2M further restricts which agents a credential can invoke
- Revoked credentials are rejected immediately
- OAuth 2.1 for Claude hosted connectors is planned for a later phase
