# Agent task vs realtime streaming (chat)

This doc explains the two chat execution paths in this repo:

- **Realtime streaming path**: Socket.IO → streaming server → model stream → incremental UI updates.
- **Agent-task path**: HTTP request → Celery task (`conversation_agent_task`) → AgentLoop (tools) → events → UI updates.

It also documents the **on-demand attachments** design for the agent-task path.

## High-level comparison

| Topic | Realtime streaming | Agent-task |
|---|---|---|
| **Transport** | Socket.IO (bi-directional) | HTTP trigger + async events |
| **Execution** | Streaming server runs the model call directly | Celery runs `conversation_agent_task` |
| **Output** | Token-by-token streaming | Step/iteration events + final message versions |
| **Tools** | Not tool-driven (today) | Tool-driven via `AgentLoop` |
| **Attachments** | Images can be appended to the user message; RAG docs often injected as text | Attachments passed as **references** (`attachment_id`) and read **on demand** via tool |
| **Persistence** | Messages persisted through streaming pipeline | User message persisted in `conversation_agent_task`; agent sessions persisted as `AgentSession` |

## Realtime streaming path (how it works)

### Frontend → Socket.IO

In the normal (non agent-task) path, the frontend emits a `message` event (see `streaming/client/src/routes/chat/page.tsx`).

Payload includes:
- the user message
- recent conversation context (bounded by `max_memory_messages`)
- plugin flags (web search, rag, etc.)
- attachments (images are typically passed as data URLs)

### Streaming server → model streaming

The streaming server uses a streaming factory that yields incremental text deltas.

Core implementation:
- `streaming/server/utils/completions.py` (`TextStreamingFactory.stream_openai`)
  - builds the message list (system + prev turns + current turn)
  - **if there are image attachments**, it builds a multimodal message with `input_text` + `input_image` parts
  - streams output via OpenAI Responses streaming API

### Streaming server → frontend events

The frontend listens for events like:
- `response` (incremental tokens)
- `responseFinished` (end of response; IDs/metadata updates)

These are emitted by the streaming server (see `streaming/server/event_triggers.py`).

## Agent-task path (how it works)

### Frontend → HTTP trigger

The frontend calls:
- `POST /v1/ai_layers/agent-task/conversation/` (see `api/ai_layers/urls.py`, `api/ai_layers/views.py`)

Payload includes:
- `conversation_id`
- `agent_slugs[]` (which agents to run, in order)
- `user_inputs[]`
- `tool_names[]`
- `multiagentic_modality`

### Backend → Celery task

`api/ai_layers/views.py` enqueues:
- `api/ai_layers/tasks.py:conversation_agent_task.delay(...)`

The task:
- loads the conversation
- normalizes inputs
- saves a user `Message`
- resolves the requested agents
- builds an `AgentLoop` and runs it per agent
- persists per-agent runs as `AgentSession`
- emits real-time events to the frontend

### Backend → events to frontend

The task emits events via `notify_user(...)` to:
- `agent_events_channel` (progress events, version readiness, errors)
- `agent_loop_finished` (final summary / done signal)

The frontend listens on the same Socket.IO connection:
- `streaming/client/src/routes/chat/page.tsx`
- `streaming/client/src/components/AgentTaskListener/AgentTaskListener.tsx`

## Agent-task inputs (strict contract)

The agent-task path uses a strict minimal shape:

```json
[
  { "type": "input_text", "text": "..." },
  { "type": "input_attachment", "attachment_id": "uuid" }
]
```

Notes:
- The saved user message text is **only** `input_text`.
- Attachments are **not** appended into the user message text.

## Attachments in agent-task (on-demand reading)

### Why references (not full text)

For the agent-task path, documents should **not** be injected into prompt context as full text because:
- large documents blow up tokens and latency
- many tasks only need a small subset of the document
- access control and auditing are easier when all reads go through one tool

### Storage model

We use `api/messaging/models.py:MessageAttachment` as a typed attachment table:
- `kind="file"`: has a `file` (images, PDFs, etc.), expires by default
- `kind="rag_document"`: references a RAG `Document` (persistent), no file
- `kind="website"`: stores a URL, no file

### Endpoints

- **Upload file attachments** (data URLs only):\n  `POST /v1/messaging/attachments/upload/`\n  Stores `MessageAttachment(kind=\"file\")`.

- **Link reference attachments** (no file):\n  `POST /v1/messaging/attachments/link/`\n  Creates `MessageAttachment(kind=\"rag_document\"|\"website\")`.

### Frontend behavior

On send (agent-task path):
- attachments with `content` starting with `data:` → uploaded via `/attachments/upload/` → returned UUIDs become `input_attachment`.
- existing RAG docs (have `id` but no `data:` content) → linked via `/attachments/link/` → returned UUID becomes `input_attachment`.

### Tool: `read_attachment`

The agent-task path enables a tool:
- `read_attachment(attachment_id, question)`

Implementation:
- `api/ai_layers/tools/read_attachment.py`

Behavior:
- validates the attachment belongs to the conversation (and user when available)
- routes by attachment kind:
  - `file`: sends the file to OpenAI (vision for images; `input_file` for docs)
  - `rag_document`: sends `Document.text` to OpenAI (with a size cap)
  - `website`: fetches URL, extracts plain text, sends to OpenAI (with a size cap)

## Known gaps / follow-ups

- **Website extraction quality**: currently very lightweight HTML stripping; could be upgraded to a more robust extractor later.
- **Large image chunking**: not implemented in this repo yet; could adopt a chunking helper like the reference project if needed.
- **Direct-to-storage uploads**: base64 upload is convenient but not ideal for large files; presigned uploads would scale better.

