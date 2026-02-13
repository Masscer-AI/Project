# Development Conventions

## Translation Keys (i18n)

**Every user-facing string must use `t()` with a translation key.** When adding new UI text, always add the corresponding keys to both locale files:

- `streaming/client/src/locales/en.json` (English)
- `streaming/client/src/locales/es.json` (Spanish)

Keys follow `kebab-case` convention (e.g. `confirm-remove-member-description`). Use `{{variable}}` for interpolation.

Spanish translations should **not** use accents (per user preference).

### Feature Flag Translation Keys

Feature flags have a special naming convention for translations:
- `ff-<flag-name>` -- Human-readable display name (e.g., `"ff-audio-tools": "Audio Tools"`)
- `ff-<flag-name>-desc` -- Short description shown as tooltip (e.g., `"ff-audio-tools-desc": "Access audio processing tools..."`)

When adding a new feature flag, always add both keys to both locale files. The registry of all flags lives in `api/authenticate/feature_flags_registry.py`.

---

## Migrations

**Migrations are handled manually by the developer, not by the AI assistant.**

When model changes are made (new fields, FK changes, etc.), the AI will:
- Modify the model code directly
- Document what changed and what migrations are needed
- **Not** run `makemigrations` or `migrate`

The developer will review the model changes and run migrations when comfortable:

```bash
python manage.py makemigrations
python manage.py migrate
```
