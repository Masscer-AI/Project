# llm_docs

Documentation written for AI assistants (Claude Code, Cursor, etc.) working on this codebase.

## What belongs here

- **Conventions**: project rules that aren't obvious from the code.
- **Testing methodology**: how to prove a change works.
- **Business logic**: the rules of a feature, who can do what, and the edge cases.

## What doesn't belong here

- Architecture write-ups, model field lists, and endpoint tables. The code already shows those, and copies go stale.
- Temporary debugging notes.

## Current documents

| File | Description |
|------|-------------|
| `conventions.md` | Code style, user-facing text, migrations, feature flags, and checklists for adding tools, pages, and WhatsApp templates |
| `testing.md` | Writing and running backend tests, and checking changes in the running dev app |
| `pld.md` | PLD rules: who goes first, run history, and what gets frozen when a run finishes |

## How to maintain

- Update a doc in the same change as the code it describes.
- Keep a "Known Gaps" section in each doc, so future sessions know what's missing without re-analyzing.
- One doc per topic.
