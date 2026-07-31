# Pending features

Track product/engineering work that is confirmed feasible but not built yet.

## WhatsApp Business profile picture API

**Status:** Not started  
**Confirmed:** Yes — Meta Cloud API supports this.

### Goal

Allow Masscer to update a WhatsApp Business phone number’s profile picture (and optionally other business profile fields) from our app/admin, instead of only via Meta Business Suite / WhatsApp Manager.

### Meta API

- Endpoint: `POST /{phone-number-id}/whatsapp_business_profile`
- Related: read profile via `GET /{phone-number-id}/whatsapp_business_profile`
- Profile picture typically requires uploading media first, then referencing the media handle in the profile update.
- Docs: [WhatsApp Business Profile](https://developers.facebook.com/docs/whatsapp/cloud-api/reference/business-profiles)

### Suggested Masscer work

1. Backend helper in `server/api/whatsapp/` (Graph upload + profile update using the line’s `platform_id` / token).
2. Authenticated API on `WSNumber` (org-scoped), e.g. set/clear profile picture.
3. Optional UI under WhatsApp line settings (“Personalizar linea”).
4. Pulumi/IAM: no new secrets if the existing WhatsApp Graph token already has the required permissions; verify token scopes before shipping.

### Out of scope for now

- Changing Meta display name verification flow
- Consumer (personal) WhatsApp profile pictures (not applicable to Cloud API business lines)
