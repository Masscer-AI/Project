# llm_docs

This directory contains **living documentation written for LLM assistants** (Cursor, Copilot, etc.) to consume as context when working on this codebase.

## Why this exists

Code alone doesn't capture architectural decisions, implicit conventions, or the "why" behind design choices. These docs bridge that gap so that any AI assistant -- or new developer -- can quickly understand how things work without reverse-engineering the entire codebase.

## What belongs here

- **System overviews** -- end-to-end explanations of major features (data model, API, frontend, permissions).
- **Conventions** -- project-specific rules that aren't obvious from the code (e.g., who runs migrations, naming patterns).
- **Architecture decisions** -- trade-offs, known gaps, and rationale for current design choices.

## What does NOT belong here

- Auto-generated API docs (use tools like Swagger/drf-spectacular for that).
- Temporary debugging notes (use `.cursor/knowledge/issues/` instead).
- Duplicating what's already obvious from the code -- these docs should add context, not restate code.

## Current documents

| File | Description |
|------|-------------|
| `conventions.md` | Project-wide development conventions (migration policy, etc.) |
| `organization-management.md` | Full breakdown of the organization system: models, API, permissions, RBAC, member lifecycle |

## How to maintain

- **Update docs when making related code changes.** If you add a new endpoint to organization management, update `organization-management.md`.
- **Keep a "Known Gaps" section** in each feature doc. It helps future sessions know what's missing without re-analyzing.
- **One doc per major feature/domain.** Don't cram everything into a single file.
