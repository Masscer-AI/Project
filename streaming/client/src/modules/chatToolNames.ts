/**
 * Former client-side chat required baseline.
 * Web chat now auto-injects these server-side in conversation_agent_task;
 * keep the list here for documentation / shared reference only.
 */
export const CHAT_REQUIRED_TOOL_NAMES = [
  "read_attachment",
  "list_attachments",
  "generate_document_file",
  "send_email",
  "list_organization_members",
  "list_organization_roles",
] as const;
