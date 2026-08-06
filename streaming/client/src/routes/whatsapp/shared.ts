export type WhatsappAccessMode = "public" | "organization" | "roles" | "user";

export type WhatsappLine = {
  id: number;
  number: string;
  agent: { name: string; slug: string };
  conversations_count: number;
  name: string | null;
  verified?: boolean;
  organization?: number | string | null;
  capabilities?: { name?: string; type?: string; enabled?: boolean }[] | null;
  access_mode?: WhatsappAccessMode;
  access_user_id?: number | null;
  allowed_roles?: { id: string; name: string }[];
};

export function formatWhatsappPhone(number: string): string {
  const digits = (number || "").replace(/\D/g, "");
  if (!digits) return number || "";
  return digits.startsWith("+") ? digits : `+${digits}`;
}

export function countEnabledCapabilities(
  capabilities: WhatsappLine["capabilities"]
): number {
  if (!capabilities?.length) return 0;
  return capabilities.filter((c) => c?.enabled).length;
}

/**
 * All agent tools that can be toggled on a WhatsApp line (Personalizar linea).
 * Matches list_available_tools() (TOOL_REGISTRY minus dependent tools like list_voices).
 * Required tools stay on; everything else is optional at the owner's risk.
 */
export const WHATSAPP_CAPABILITY_NAMES = [
  // Always on (backend-enforced)
  "read_attachment",
  "list_attachments",
  "list_document_templates",
  "render_document_template",
  "raise_alert",
  "query_organization_tags",
  "create_organization_tag",
  "change_conversation_tags",
  "change_conversation_summary",
  "get_tag_context",
  "query_conversation",
  // Common optional
  "explore_web",
  "rag_query",
  "create_image",
  "create_speech",
  "generate_dialogue",
  "generate_video",
  "generate_document_file",
  "generate_excel_file",
  "generate_gamma_presentation",
  "list_whatsapp_resources",
  "list_whatsapp_templates",
  "send_ws_template_message",
  // Advanced (under owner's risk)
  "send_email",
  "list_organization_members",
  "list_organization_roles",
  "list_conversations",
  "list_calendar_events",
  "create_calendar_event",
  "update_calendar_event",
  "schedule_task",
  "list_scheduled_tasks",
  "cancel_scheduled_task",
  "read_plugin_instructions",
  "create_completion",
] as const;

export const WHATSAPP_REQUIRED_CAPABILITY_NAMES = [
  "read_attachment",
  "list_attachments",
  "list_document_templates",
  "render_document_template",
  "raise_alert",
  "query_organization_tags",
  "create_organization_tag",
  "change_conversation_tags",
  "change_conversation_summary",
  "get_tag_context",
  "query_conversation",
] as const;

export const WHATSAPP_REQUIRED_CAPABILITY_SET = new Set<string>(
  WHATSAPP_REQUIRED_CAPABILITY_NAMES
);

export function buildInitialCapabilityState(
  capabilities: { name?: string; type?: string; enabled?: boolean }[] | null | undefined
): Record<string, boolean> {
  const initial: Record<string, boolean> = {};
  for (const n of WHATSAPP_CAPABILITY_NAMES) initial[n] = false;
  for (const c of capabilities ?? []) {
    if (c?.name) initial[c.name] = Boolean(c.enabled);
  }
  for (const requiredName of WHATSAPP_REQUIRED_CAPABILITY_NAMES) {
    initial[requiredName] = true;
  }
  return initial;
}

export function buildCapabilitiesPayload(
  capabilityState: Record<string, boolean>
): { name: string; type: "internal_tool"; enabled: boolean }[] {
  return WHATSAPP_CAPABILITY_NAMES.map((name) => ({
    name,
    type: "internal_tool" as const,
    enabled: capabilityState[name] ?? false,
  }));
}
