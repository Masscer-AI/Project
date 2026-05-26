# WhatsApp number setup guide

End-to-end process to add a new WhatsApp business line: first in **Meta WhatsApp Manager**, then in **Masscer Django admin** so inbound messages route to the correct agent.

Provisioning is intentionally **admin-only** today. After the line exists, org users with the `whatsapp-numbers-management` feature flag can customize agent, display name, and tool capabilities from the app (`/whatsapp`).

---

## Prerequisites

Before starting, confirm server environment variables are set (see `.env.example`):

| Variable | Purpose |
|----------|---------|
| `WHATSAPP_GRAPH_API_TOKEN` | System user token for Graph API (register phone, WABA subscribe) |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Meta webhook verification string |
| `WHATSAPP_APP_SECRET` | Required for app-level webhook subscription calls |
| `API_BASE_URL` or `API_URL` | Public HTTPS origin of the API (e.g. dev tunnel). Meta calls `{base}/v1/whatsapp/webhook` |

You also need:

- Django admin access
- An **Agent** already created (and assigned to the target **Organization** if the line is org-owned)
- The **WABA id** for the Masscer AI account: `418328741371703` (from the WhatsApp Manager URL `asset_id` parameter)

---

## Part 1 — Add and verify the number in Meta

### 1. Open WhatsApp Manager

Go to the phone numbers page for the Masscer AI WABA:

[WhatsApp Manager — Phone numbers](https://business.facebook.com/latest/whatsapp_manager/phone_numbers/?business_id=1207679763830645&tab=phone-numbers&nav_ref=whatsapp_manager&asset_id=418328741371703)

Confirm the account selector shows **Masscer AI** (WABA / asset id `418328741371703`).

### 2. Start “Add phone number”

Click the blue **Add phone number** button.

### 3. Business profile details

1. **Category** — Open **Choose a business category** and pick the best match from the list (e.g. Professional Services, Other). Scroll the list if needed; Meta shows many verticals (Automotive, Education, Restaurant, etc.).
2. **Description** (optional) — Short business description for the WhatsApp profile.
3. Click **Continue**.

### 4. Enter the phone number

1. Select **country** (e.g. Mexico).
2. Enter the phone number (without duplicating the country code if the UI already applies it).
3. Complete Meta’s flow until the number appears in the phone numbers list.

### 5. Verify the number

1. In the list, select the new line.
2. Open the **Profile** tab.
3. If you see **Phone number verification required**, click **Send verification code**.
4. Complete verification on the device (SMS or voice, per Meta’s prompt).

Do not continue to Masscer admin until Meta shows the number as verified and able to send messages.

### 6. Note the Phone number ID

On the number’s detail/header area, Meta shows **Phone number ID** (numeric string). Copy it — this becomes `platform_id` in Django.

Example from a real line:

| Field | Example value |
|-------|----------------|
| Display | `MX +52 1 729 124 0995` |
| Display name | `Asesoría Legal Integral` |
| **Phone number ID** | `575088399024656` |

Store the **Phone number ID** somewhere safe; you cannot complete Masscer setup without it.

For the `number` field in Django, store digits only (no `+` or spaces), country code included, max **15 characters** on the model — e.g. `5217291240995`.

---

## Part 2 — Connect the number in Masscer (Django admin)

### 1. Open WSNumber admin

Django admin → **WhatsApp** → **WS numbers** → **Add WS number** (or edit an existing row).

Admin change form also shows the **Webhook callback URL** preview (`{API_BASE_URL}/v1/whatsapp/webhook`) — the same URL used when you run **Setup WABA & webhook**.

### 2. Fill required and recommended fields

| Field | Required | What to enter |
|-------|----------|----------------|
| **Organization** | Recommended | Org that owns the line (billing + `/whatsapp` visibility). Leave **User** empty when using org ownership. |
| **User** | Optional | Legacy personal ownership. Use **either** Organization **or** User, not both, for new lines. |
| **Agent** | **Yes** | Agent that replies on this WhatsApp line. |
| **Name** | Optional | Friendly label in admin and app (e.g. `Asesoría Legal Integral`). |
| **Number** | **Yes** | E.164-style digits only, ≤15 chars (e.g. `5217291240995`). Used in API paths: `PUT /v1/whatsapp/numbers/<number>`. |
| **Platform id** | **Yes** | Meta **Phone number ID** from Part 1 (e.g. `575088399024656`). |
| **Waba id** | Recommended | `418328741371703` for Masscer AI. Speeds webhook setup; otherwise resolved from `platform_id` via Graph when possible. |
| **Capabilities** | Optional | JSON list of enabled internal tools. Default `[]` is fine; customize later via API or `/whatsapp` if the feature flag is on. |

**Not used in current flows (safe to leave default / empty):**

- **Verified** — not read by runtime code today.
- **Certicate b64** — legacy / unused; can be ignored or removed in a future cleanup task.

**Read-only after save:** `Created at`, `Updated at`.

### 3. Save the record

Click **Save**. You should land on the **change** form with three action buttons at the top.

---

## Part 3 — Register phone and configure webhooks

Run these **in order** on the saved WSNumber change page (POST buttons in the admin header).

### 1. Register phone number

Click **Register phone number**.

- Calls Meta Graph: `POST {platform_id}/register` with a generated 6-digit PIN.
- Requires `WHATSAPP_GRAPH_API_TOKEN` and a valid **Platform id**.
- If Meta returns “already registered” (error code `133005`), that is OK — continue to webhook setup.

### 2. Setup WABA & webhook

Click **Setup WABA & webhook**.

This chain:

1. Resolves **WABA id** (from the field or Graph lookup on `platform_id`).
2. Subscribes the app to the WABA (`subscribed_apps`).
3. Configures the app webhook for `whatsapp_business_account` → your public `{API_BASE_URL}/v1/whatsapp/webhook` with `WHATSAPP_WEBHOOK_VERIFY_TOKEN`.
4. Persists `waba_id` on the row if it was resolved from Graph.

Requires `WHATSAPP_GRAPH_API_TOKEN`, `WHATSAPP_APP_SECRET`, `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, and a reachable **API_BASE_URL**.

### 3. Check webhook config (optional)

Click **Check webhook config** to read back subscription summary (callback URL, active flag, fields). Use this if inbound messages do not arrive.

---

## Part 4 — Verify end-to-end

1. Send a WhatsApp message **to** the business number from a personal phone.
2. Confirm Celery processes the webhook (`async_handle_webhook`).
3. Confirm a `Conversation` exists linked to this `WSNumber` and the sender’s phone.
4. Confirm the agent reply is delivered on WhatsApp.

If webhooks never arrive:

- Re-run **Check webhook config**.
- Confirm `platform_id` on `WSNumber` matches Meta’s **Phone number ID**.
- Confirm tunnel / production `API_BASE_URL` is HTTPS and matches the callback Meta shows.

---

## Optional — Customize in the app (not provisioning)

Users with feature flag **`whatsapp-numbers-management`** can:

- `GET /v1/whatsapp/numbers` — list lines for their org
- `PUT /v1/whatsapp/numbers/<number>` — change **agent** (`slug`), **name**, **capabilities**

They **cannot** create lines or run register/webhook setup via API today.

---

## Quick reference (Masscer AI)

| Item | Value |
|------|--------|
| WhatsApp Manager URL | [Phone numbers](https://business.facebook.com/latest/whatsapp_manager/phone_numbers/?business_id=1207679763830645&tab=phone-numbers&nav_ref=whatsapp_manager&asset_id=418328741371703) |
| WABA id (`waba_id` / `asset_id`) | `418328741371703` |
| Webhook path | `/v1/whatsapp/webhook` |
| Django model | `api.whatsapp.models.WSNumber` |
| Graph helpers | `api.whatsapp.graph_webhook_setup` |

---

## Known gaps

- No REST API to create `WSNumber` or trigger register/webhook (admin only).
- `verified` and `certicate_b64` fields are unused; candidate for model/admin cleanup.
- `verify_whatsapp_number()` in `actions.py` is a stub and not part of this flow.
