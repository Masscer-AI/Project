# Organization Management

This document describes how organizations work end-to-end: data model, API layer, permission system, and frontend UI.

---

## Table of Contents

- [Data Model](#data-model)
- [How Users Join an Organization](#how-users-join-an-organization)
- [How Users Are Removed](#how-users-are-removed)
- [Permission System](#permission-system)
- [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
- [Feature Flags](#feature-flags)
- [API Reference](#api-reference)
- [Frontend Architecture](#frontend-architecture)
- [Signals & Cache Invalidation](#signals--cache-invalidation)
- [Known Gaps](#known-gaps)

---

## Data Model

All models live in `api/authenticate/models.py`.

### Entity Relationship

```
User (Django auth)
  |
  |-- 1:1 --> UserProfile
  |               |-- FK --> Organization (nullable, SET_NULL)
  |
  |-- 1:N --> RoleAssignment
                  |-- FK --> Role
                  |-- FK --> Organization
                  
Organization
  |-- FK owner --> User
  |-- 1:1 auto --> CredentialsManager (created via signal)
  |-- 1:N --> Role
  |-- 1:N --> RoleAssignment
  |-- 1:N --> FeatureFlagAssignment
```

### Organization

| Field        | Type                | Notes                                      |
|-------------|---------------------|--------------------------------------------|
| `id`        | UUID (PK)           | Auto-generated                             |
| `name`      | CharField(255)      | Required                                   |
| `description` | TextField         | Nullable                                   |
| `owner`     | FK -> User          | `on_delete=CASCADE`. The creator/admin.    |
| `timezone`  | CharField(50)       | Default `UTC`, choices from `pytz`         |
| `logo`      | ImageField          | Stored at `organizations/logos/{id}.{ext}` |
| `created_at`| DateTimeField       | Auto                                       |
| `updated_at`| DateTimeField       | Auto                                       |

**Key detail:** The `owner` field is a direct FK on the Organization model. It is **not** the same as membership. The owner always has full permissions.

### UserProfile

| Field          | Type             | Notes                                        |
|---------------|------------------|----------------------------------------------|
| `id`          | UUID (PK)        | Auto-generated                               |
| `user`        | OneToOne -> User | `related_name="profile"`                     |
| `organization`| FK -> Organization | **Nullable, SET_NULL**. `related_name="members"` |
| `is_active`   | BooleanField     | Default `True`. Deactivated users can't access org resources. |
| `name`        | CharField        | Display name                                 |
| `avatar_url`  | TextField        | Nullable                                     |
| `bio`         | TextField        | Nullable                                     |
| ...           | ...              | `sex`, `age`, `birthday` (personal fields)   |

**This is the membership link.** A user belongs to an organization when `UserProfile.organization` points to it. A user can only belong to **one organization at a time** (single FK, not M2M).

### CredentialsManager

Stores third-party API keys per organization. Auto-created via Django signal when an Organization is created.

| Field              | Type          | Notes     |
|-------------------|---------------|-----------|
| `organization`    | FK -> Org     | Required  |
| `openai_api_key`  | CharField     | Nullable  |
| `anthropic_api_key` | CharField   | Nullable  |
| `brave_api_key`   | CharField     | Nullable  |
| `pexels_api_key`  | CharField     | Nullable  |
| `elevenlabs_api_key` | CharField  | Nullable  |
| `heygen_api_key`  | CharField     | Nullable  |

### Role

| Field          | Type          | Notes                                        |
|---------------|---------------|----------------------------------------------|
| `id`          | UUID (PK)     |                                              |
| `organization`| FK -> Org     | Scoped per organization                      |
| `name`        | CharField(50) | Unique per organization (`unique_together`)  |
| `description` | TextField     | Nullable                                     |
| `enabled`     | BooleanField  | Default `True`                               |
| `capabilities`| JSONField     | List of feature flag name strings            |

### RoleAssignment

| Field          | Type          | Notes                                          |
|---------------|---------------|-------------------------------------------------|
| `id`          | UUID (PK)     |                                                |
| `user`        | FK -> User    |                                                |
| `organization`| FK -> Org     |                                                |
| `role`        | FK -> Role    |                                                |
| `from_date`   | DateField     | When the assignment starts                     |
| `to_date`     | DateField     | Nullable. If null, active indefinitely         |

**Active assignment** = `from_date <= today AND (to_date IS NULL OR to_date >= today)`

---

## How Users Join an Organization

There are **two paths** for a user to join an organization, both handled during signup (`api/authenticate/serializers.py` -> `SignupSerializer`).

### Path 1: Create a New Organization (owner signup)

1. User signs up providing `organization_name` (no `organization_id`).
2. `SignupSerializer.create()` creates the `User` record.
3. A new `Organization` is created with `owner=user`.
4. A `UserProfile` is created/fetched and `profile.organization` is set to the new org.
5. Django signal auto-creates a `CredentialsManager` for the new org.

**Result:** The user is both the `owner` and a `member` (via profile).

### Path 2: Join an Existing Organization (invite signup)

1. An existing organization member/owner generates an **invite link** from the frontend:
   ```
   {origin}/signup?orgId={organization_id}
   ```
2. The invited user opens the link. The frontend reads the `orgId` query parameter and fetches organization info (`GET /v1/auth/signup?orgId={orgId}`).
3. The signup form hides the "organization name" field and shows the org's logo/name/description instead.
4. User submits the signup form with `organization_id`.
5. `SignupSerializer.create()` creates the `User`, fetches the existing organization, creates a `UserProfile` with `profile.organization = existing_org`.

**Result:** The user becomes a member (via profile) but is **not** the owner.

### Important Constraints

- `organization_id` and `organization_name` are **mutually exclusive** -- you must provide exactly one.
- The invite link is a simple URL with the org UUID. There is no token-based invitation system or expiration.
- A QR code is also generated on the frontend for the invite link.

---

## How Users Are Removed

Two operations are supported: **deactivation** (soft, reversible) and **full removal** (hard, with cleanup).

See the [Member Deactivation & Removal](#member-deactivation--removal) section for full details.

### Summary

- **Deactivate:** `PATCH /organizations/{id}/members/{user_id}/` with `{"is_active": false}`. Member stays linked but loses all access. Reversible.
- **Remove:** `DELETE /organizations/{id}/members/{user_id}/`. Unlinks the member, cleans up role assignments and alert subscriptions. Not reversible (user would need to re-join via invite).
- The **owner cannot be deactivated or removed**. They must transfer ownership or delete the org.
- **Conversations stay with the organization** (`Conversation.organization` FK). The `user` FK uses `SET_NULL`.

---

## Permission System

Defined in `api/authenticate/views.py`:

```python
def _can_manage_organization(user, organization):
    if organization.owner_id == user.id:
        return True
    enabled, _ = FeatureFlagService.is_feature_enabled(
        feature_flag_name="manage-organization",
        organization=organization,
        user=user,
    )
    return enabled
```

### Permission Tiers

| Action                          | Owner | `manage-organization` flag | Regular member |
|--------------------------------|-------|---------------------------|----------------|
| View organization              | Yes   | Yes                       | No (403)       |
| Update name / description      | Yes   | Yes                       | No             |
| Upload / delete logo           | Yes   | Yes                       | No             |
| View / update credentials      | Yes   | No (owner only)           | No             |
| Delete organization            | Yes   | No (owner only)           | No             |
| View members                   | Yes   | Yes                       | No             |
| Manage roles                   | Yes   | Yes                       | No             |
| Manage role assignments        | Yes   | Yes                       | No             |

### How Organization Ownership is Determined

- `Organization.owner` is a direct FK to `User`.
- The owner is set at creation time and cannot be transferred via the API (no endpoint for this).

---

## Role-Based Access Control (RBAC)

Roles are organization-scoped containers of capabilities (feature flag names).

### How It Works

1. **Admin creates a Role** with a list of `capabilities` (feature flag names).
2. **Admin assigns the Role** to a user via a `RoleAssignment` with a `from_date` (and optional `to_date`).
3. When checking if a feature is enabled for a user, the system checks if any of the user's active roles contain that feature flag name in their `capabilities` list.

### Assignment Rules

- A `RoleAssignment` has a date range (`from_date` to `to_date`).
- If `to_date` is `null`, the assignment is active indefinitely.
- Only `organization_only=False` feature flags can be used as role capabilities.
- Roles are unique by `(organization, name)`.

### Frontend Flow

1. On the **Roles tab**, the admin can create/edit/delete roles.
2. On the **Members tab**, each non-owner member has a role dropdown.
3. Selecting a role triggers `POST /organizations/{id}/roles/assignments/` with the user and role IDs.
4. Changing a role first removes the old assignment (`DELETE`) then creates a new one.

---

## Feature Flags

Managed by `FeatureFlagService` in `api/authenticate/services.py`.

### Resolution Priority

When checking `is_feature_enabled(flag_name, organization, user)`:

| Priority | Check                            | Scope                    |
|----------|----------------------------------|--------------------------|
| 1        | Is user an organization owner?   | All flags -> `True`      |
| 2        | Direct user-level assignment     | Specific flag            |
| 3        | Active role capability           | Via `RoleAssignment`     |
| 4        | Organization-level assignment    | Only `organization_only` flags |
| 5        | Default                          | `False`                  |

### Feature Flags Registry

All feature flags are defined in `api/authenticate/feature_flags_registry.py` (`KNOWN_FEATURE_FLAGS` dict). A management command syncs them to the database on startup, so this file is the **single source of truth** for which flags exist.

When adding a new feature flag:
1. Add it to `KNOWN_FEATURE_FLAGS` in `feature_flags_registry.py`
2. Add translation keys `ff-<name>` and `ff-<name>-desc` to both `en.json` and `es.json`
3. The frontend uses `t("ff-<name>")` for display names and `t("ff-<name>-desc")` for tooltip descriptions

| Flag | Org-only | Purpose |
|------|----------|---------|
| `manage-organization` | No | Manage org settings, members, roles |
| `alert-rules-manager` | No | Create/manage conversation alert rules |
| `tags-management` | No | Create/manage conversation tags |
| `conversations-dashboard` | No | Access the conversations dashboard |
| `edit-organization-agent` | No | Edit org-owned agent configs |
| `conversation-analysis` | **Yes** | Automatic AI conversation analysis |
| `chat-widgets-management` | No | Create/manage embeddable chat widgets |
| `train-agents` | No | Upload docs & train agents |
| `audio-tools` | No | Transcription & text-to-speech |
| `image-tools` | No | Image generation & editing |
| `video-tools` | No | Video generation & processing |
| `web-scraping` | No | Extract content from URLs |
| `add-files-to-chat` | No | Upload files to conversations |
| `transcribe-on-chat` | No | Voice-to-text in chat input |
| `chat-generate-speech` | No | Generate speech from messages |
| `multi-agent-chat` | No | Multi-agent conversations |
| `add-llm` | No | Configure custom LLM connections |
| `set-agent-ownership` | No | Transfer agent ownership to org |

### Org-Only Flags

Feature flags with `organization_only=True`:
- Can only be assigned at the organization level (not to individual users).
- Cannot be used as role capabilities.
- Are checked at priority 4 (org-level assignment).
- Currently only `conversation-analysis` has this flag.

---

## API Reference

Base path: `/v1/auth/`

All endpoints require `@token_required` (Authorization header with JWT).

### Organizations

| Method   | Path                                          | Description                          | Permission         |
|----------|-----------------------------------------------|--------------------------------------|-------------------|
| `GET`    | `/organizations/`                             | List user's organizations            | Authenticated     |
| `POST`   | `/organizations/`                             | Create new organization              | Authenticated     |
| `PUT`    | `/organizations/{id}/`                        | Update org (name, description, logo) | Owner or `manage-organization` |
| `DELETE` | `/organizations/{id}/`                        | Delete organization                  | Owner only        |

### Credentials

| Method   | Path                                          | Description                          | Permission   |
|----------|-----------------------------------------------|--------------------------------------|-------------|
| `GET`    | `/organizations/{id}/credentials/`            | Get API keys                         | Owner only  |
| `PUT`    | `/organizations/{id}/credentials/`            | Update API keys                      | Owner only  |

### Members

| Method   | Path                                              | Description                          | Permission                    |
|----------|---------------------------------------------------|--------------------------------------|------------------------------|
| `GET`    | `/organizations/{id}/members/`                    | List all members (owner + profiles)  | Owner or `manage-organization` |
| `PATCH`  | `/organizations/{id}/members/{user_id}/`          | Deactivate / reactivate member       | Owner or `manage-organization` |
| `DELETE` | `/organizations/{id}/members/{user_id}/`          | Fully remove member from org         | Owner or `manage-organization` |

### Roles

| Method   | Path                                          | Description         | Permission                    |
|----------|-----------------------------------------------|---------------------|------------------------------|
| `GET`    | `/organizations/{id}/roles/`                  | List roles          | Owner or `manage-organization` |
| `POST`   | `/organizations/{id}/roles/`                  | Create role         | Owner or `manage-organization` |
| `GET`    | `/organizations/{id}/roles/{role_id}/`        | Get role detail     | Owner or `manage-organization` |
| `PUT`    | `/organizations/{id}/roles/{role_id}/`        | Update role         | Owner or `manage-organization` |
| `DELETE` | `/organizations/{id}/roles/{role_id}/`        | Delete role         | Owner or `manage-organization` |

### Role Assignments

| Method   | Path                                              | Description            | Permission                    |
|----------|----------------------------------------------------|------------------------|------------------------------|
| `GET`    | `/organizations/{id}/roles/assignments/`           | List assignments       | Owner or `manage-organization` |
| `POST`   | `/organizations/{id}/roles/assignments/`           | Assign role to user    | Owner or `manage-organization` |
| `DELETE` | `/organizations/{id}/roles/assignments/?assignment_id={id}` | Remove assignment | Owner or `manage-organization` |

### Feature Flags

| Method   | Path                                    | Description                       | Permission    |
|----------|-----------------------------------------|-----------------------------------|--------------|
| `GET`    | `/feature-flags/names/`                 | List all flag names               | Authenticated |
| `GET`    | `/feature-flags/{name}/check`           | Check if flag enabled for user    | Authenticated |
| `GET`    | `/feature-flags/`                       | Get all flags for user's orgs     | Authenticated |

---

## Frontend Architecture

### Key Files

| File                                            | Purpose                                 |
|-------------------------------------------------|-----------------------------------------|
| `streaming/client/src/routes/organization/page.tsx` | Main organization management page   |
| `streaming/client/src/routes/signup/page.tsx`   | Handles invite-based signup             |
| `streaming/client/src/modules/apiCalls.ts`      | API client functions                    |
| `streaming/client/src/modules/store.tsx`        | Zustand store (has `organizations` field) |
| `streaming/client/src/components/Sidebar/Sidebar.tsx` | Nav with "Manage Organization" button |
| `streaming/client/src/components/QRGenerator/QRGenerator.tsx` | QR code for invite links |

### Page Structure

The organization page (`/organization`) has three tabs:

#### Settings Tab
- Logo upload / removal (FileButton)
- Organization name (TextInput)
- Organization description (Textarea)
- Save / Cancel buttons

#### Roles Tab
- List of existing roles with name, description, capabilities (as badges)
- Create role button opens a modal
- Edit / Delete buttons per role
- Role modal: name, description, capabilities checkboxes (sourced from feature flag names)

#### Members Tab
- **Invite section:** toggle to show invite URL + QR code (180x180px)
- **Members list:** card per member showing:
  - Profile name / username / email
  - "Owner" badge if applicable
  - Role dropdown (only for non-owner members)

### Access Control in UI

- The "Manage Organization" button in the sidebar only appears if `orgs.some(o => o.is_owner || o.can_manage)`.
- The organization page filters to show only orgs where the user `is_owner` or `can_manage`.
- Owner members don't get a role dropdown (they have full access automatically).

### State Management

- Local React state (`useState`) for members, roles, feature flags, loading states.
- Mantine `useForm` for organization settings and role creation.
- No optimistic updates -- mutations trigger refetches.
- Toast notifications for success/error feedback.

---

## Signals & Cache Invalidation

Defined in `api/authenticate/signals.py`.

| Signal                  | Trigger                                  | Effect                                              |
|------------------------|------------------------------------------|-----------------------------------------------------|
| Organization `post_save` (created) | New organization created        | Auto-creates `CredentialsManager`                   |
| FeatureFlag save/delete | Any feature flag change                  | Invalidates global `feature_flag_names` cache       |
| FeatureFlagAssignment save/delete | Flag assignment change          | Invalidates cache for affected user or all org members |
| Role `post_save`       | Role capabilities changed                | Invalidates cache for all users holding that role   |
| RoleAssignment save/delete | Role assignment change                | Invalidates cache for the affected user             |

Cache keys follow the pattern:
- `ff_list_{user_id}` -- user's flag list
- `ff_check_{user_id}_{flag_name}` -- individual flag check
- `feature_flag_names` -- global flag names

---

## Member Deactivation & Removal

### Deactivation (soft removal)

`UserProfile.is_active` controls whether a member can access organization resources.

| State            | `organization` | `is_active` | Can access org? |
|-----------------|----------------|-------------|-----------------|
| Active member   | set            | `True`      | Yes             |
| Deactivated     | set            | `False`     | No              |
| Fully removed   | `null`         | `True`      | No (no link)    |

**Endpoint:** `PATCH /organizations/{id}/members/{user_id}/`
- Body: `{"is_active": false}` to deactivate, `{"is_active": true}` to reactivate
- Permission: Owner or `manage-organization` flag
- Cannot deactivate the owner

**What deactivation blocks:**
- Organization listing (`OrganizationView.get`) filters out orgs where `is_active=False`
- `_can_manage_organization()` returns `False` for deactivated members
- All org-scoped endpoints that call `_can_manage_organization()` are blocked
- Frontend disables the role dropdown and shows a "Deactivated" badge

**What deactivation preserves:**
- The `UserProfile.organization` FK stays linked (can be reactivated)
- Conversations remain (they belong to the org via `Conversation.organization`)
- Role assignments remain (can be reactivated instantly)

### Full Removal

**Endpoint:** `DELETE /organizations/{id}/members/{user_id}/`
- Permission: Owner or `manage-organization` flag
- Cannot remove the owner

**Cleanup performed on removal:**
1. `RoleAssignment` records for user+org are deleted
2. User is removed from `ConversationAlertRule.selected_members` (M2M)
3. `AlertSubscription` records for the org's rules are deleted
4. `UserProfile.organization` is set to `null`
5. `UserProfile.is_active` is reset to `True` (clean slate for future orgs)

**What removal preserves:**
- The Django `User` account (user can sign up to another org)
- `Conversation` records (they have `organization` FK; `user` FK is `SET_NULL`-safe)

### Conversation Ownership Model

`Conversation` now has an `organization` FK (`on_delete=CASCADE`). Conversations belong to the organization, not the user. The `user` FK tracks who participated but uses `on_delete=SET_NULL` so removing/deleting a user doesn't delete org conversations.

**Migration needed:** Backfill `Conversation.organization` from `user.profile.organization` for existing records.

### Frontend Controls

Each non-owner member card now shows:
- **Pause icon** (yellow) -- deactivate the member
- **Play icon** (green) -- reactivate a deactivated member (replaces pause)
- **Trash icon** (red) -- fully remove with confirmation dialog
- **"Deactivated" badge** -- shown on deactivated members (card is dimmed)
- Role dropdown is disabled for deactivated members

---

## Known Gaps

1. ~~No member removal endpoint~~ -- **Resolved.** `PATCH` and `DELETE` on `/organizations/{id}/members/{user_id}/`.
2. **No "Leave organization" UI** -- Members have no way to leave an organization from the frontend (only admins can remove).
3. **No ownership transfer** -- The `Organization.owner` FK cannot be changed via any API endpoint.
4. **Invite links have no expiration or revocation** -- The invite URL is just `{origin}/signup?orgId={uuid}`, always valid as long as the org exists.
5. **Single organization per user** -- `UserProfile.organization` is a single FK, so a user can only belong to one organization at a time.
6. **No organization deletion UI** -- The `DELETE` endpoint exists but has no frontend button.
7. **No member search/filter** -- The members list has no search or pagination.
8. **Credentials restricted to owner** -- Even users with `manage-organization` cannot view/edit API credentials.
9. **Backfill migration needed** -- Existing `Conversation` records need `organization` populated from `user.profile.organization`.
