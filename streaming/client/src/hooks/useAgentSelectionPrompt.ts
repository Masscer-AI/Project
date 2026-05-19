import { useCallback, useEffect, useRef } from "react";
import { useDisclosure } from "@mantine/hooks";

type UseAgentSelectionPromptOptions = {
  conversationId: string | undefined;
  /** When false (viewer/read-only), the modal is never auto-opened. */
  enabled: boolean;
  hasAgents: boolean;
  selectedAgentCount: number;
  messageCount: number;
  /** When true, close the modal as soon as at least one agent is selected. */
  closeOnFirstSelection?: boolean;
};

/**
 * Auto-opens the agents modal on empty chats with no selection.
 * Remembers dismissal per conversation so closing without selecting does not loop.
 */
export function useAgentSelectionPrompt({
  conversationId,
  enabled,
  hasAgents,
  selectedAgentCount,
  messageCount,
  closeOnFirstSelection = false,
}: UseAgentSelectionPromptOptions) {
  const [opened, { open, close }] = useDisclosure(false);
  const dismissedForConversationRef = useRef<string | null>(null);

  useEffect(() => {
    dismissedForConversationRef.current = null;
  }, [conversationId]);

  const shouldPrompt =
    enabled &&
    hasAgents &&
    selectedAgentCount === 0 &&
    messageCount === 0 &&
    Boolean(conversationId);

  useEffect(() => {
    if (!shouldPrompt || !conversationId) return;
    if (dismissedForConversationRef.current === conversationId) return;
    open();
  }, [shouldPrompt, conversationId, open]);

  useEffect(() => {
    if (closeOnFirstSelection && selectedAgentCount > 0 && opened) {
      close();
    }
  }, [closeOnFirstSelection, selectedAgentCount, opened, close]);

  const handleClose = useCallback(() => {
    if (conversationId) {
      dismissedForConversationRef.current = conversationId;
    }
    close();
  }, [conversationId, close]);

  return {
    opened,
    open,
    close: handleClose,
  };
}
