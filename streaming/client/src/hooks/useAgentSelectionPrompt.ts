import { useCallback, useEffect, useRef } from "react";
import { useDisclosure } from "@mantine/hooks";

type UseAgentSelectionPromptOptions = {
  conversationId: string | undefined;
  enabled: boolean;
  hasAgents: boolean;
  selectedAgentCount: number;
  messageCount: number;
  closeOnFirstSelection?: boolean;
};

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
  const prevSelectedCountRef = useRef(selectedAgentCount);

  useEffect(() => {
    dismissedForConversationRef.current = null;
    prevSelectedCountRef.current = selectedAgentCount;
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
    const prevCount = prevSelectedCountRef.current;
    prevSelectedCountRef.current = selectedAgentCount;
    if (
      closeOnFirstSelection &&
      opened &&
      prevCount === 0 &&
      selectedAgentCount > 0
    ) {
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
