import React, { useEffect, useState } from "react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import "./page.css";
import {
  getWhatsappConversations,
  getWhatsappConversationMessages,
  getWhatsappNumbers,
  sendMessageToConversation,
  updateWhatsappNumber,
} from "../../modules/apiCalls";
import MarkdownRenderer from "../../components/MarkdownRenderer/MarkdownRenderer";
import { AgentSelector } from "../../components/AgentSelector/AgentSelector";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { useDisclosure } from "@mantine/hooks";

import {
  ActionIcon,
  Box,
  Button,
  Card,
  Checkbox,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { IconMenu2, IconSend, IconDeviceFloppy } from "@tabler/icons-react";

/** Tools that make sense on WhatsApp (no plugins / doc templates — web UI only). */
const WHATSAPP_CAPABILITY_NAMES = [
  "read_attachment",
  "list_attachments",
  "explore_web",
  "rag_query",
  "create_image",
  "create_speech",
  "generate_video",
] as const;

function buildCapabilitiesPayload(
  capabilityState: Record<string, boolean>
): { name: string; type: "internal_tool"; enabled: boolean }[] {
  return WHATSAPP_CAPABILITY_NAMES.map((name) => ({
    name,
    type: "internal_tool",
    enabled: capabilityState[name] ?? false,
  }));
}

type WhatsappLine = {
  id: number;
  number: string;
  agent: { name: string; slug: string };
  conversations_count: number;
  name: string | null;
  capabilities?: { name?: string; type?: string; enabled?: boolean }[] | null;
};

export default function Whatsapp() {
  const { t } = useTranslation();
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));

  const [numbers, setNumbers] = useState<WhatsappLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refreshNumbers = () => {
    return getWhatsappNumbers()
      .then((res) => {
        setNumbers(res as WhatsappLine[]);
        setLoadError(null);
      })
      .catch(() => {
        setLoadError(t("whatsapp-load-error"));
      });
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getWhatsappNumbers()
      .then((res) => {
        if (!cancelled) {
          setNumbers(res as WhatsappLine[]);
          setLoadError(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError(t("whatsapp-load-error"));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  return (
    <main className="d-flex pos-relative h-viewport">
      {chatState.isSidebarOpened && <Sidebar />}
      <div
        style={{
          flex: "1 1 auto",
          minWidth: 0,
          padding: 24,
          overflowY: "auto",
          minHeight: "100vh",
          display: "flex",
          justifyContent: "center",
        }}
        className="relative"
      >
        {!chatState.isSidebarOpened && (
          <Box pos="absolute" top={24} left={24} style={{ zIndex: 10 }}>
            <ActionIcon variant="subtle" color="gray" onClick={toggleSidebar}>
              <IconMenu2 size={20} />
            </ActionIcon>
          </Box>
        )}

        <Box px="md" w="100%" maw="42rem" mx="auto">
          <Title order={2} ta="center" mb="lg" mt="md">
            {t("whatsapp")}
          </Title>
          <Text mb="md">{t("whatsapp-intro")}</Text>
          <Text size="sm" c="dimmed" mb="md">
            {t("whatsapp-provision-note")}
          </Text>

          <Title order={4} mb="sm">
            {t("whatsapp-your-numbers")}
          </Title>

          {loading ? (
            <Stack align="center" py="xl">
              <Loader color="violet" />
            </Stack>
          ) : loadError ? (
            <Text c="red">{loadError}</Text>
          ) : numbers.length === 0 ? (
            <Text c="dimmed">{t("whatsapp-empty-lines")}</Text>
          ) : (
            <Stack gap="md">
              {numbers.map((line) => (
                <WhatsAppNumber
                  key={line.id}
                  line={line}
                  onRefresh={refreshNumbers}
                />
              ))}
            </Stack>
          )}
        </Box>
      </div>
    </main>
  );
}

const WhatsAppNumber = ({
  line,
  onRefresh,
}: {
  line: WhatsappLine;
  onRefresh: () => Promise<void>;
}) => {
  const { t } = useTranslation();
  const { number, agent, conversations_count, name } = line;
  const [settingsOpened, { open: openSettings, close: closeSettings }] =
    useDisclosure(false);
  const [conversations, setConversations] = useState<any[]>([]);
  const [nameInput, setNameInput] = useState(name ?? "");
  const [capabilityState, setCapabilityState] = useState<Record<string, boolean>>(
    () => {
      const initial: Record<string, boolean> = {};
      for (const n of WHATSAPP_CAPABILITY_NAMES) initial[n] = false;
      for (const c of line.capabilities ?? []) {
        if (c?.name) initial[c.name] = Boolean(c.enabled);
      }
      return initial;
    }
  );

  useEffect(() => {
    getWhatsappConversations().then((res) => {
      setConversations(res as any[]);
    });
  }, []);

  useEffect(() => {
    if (!settingsOpened) return;
    setNameInput(line.name ?? "");
    const initial: Record<string, boolean> = {};
    for (const n of WHATSAPP_CAPABILITY_NAMES) initial[n] = false;
    for (const c of line.capabilities ?? []) {
      if (c?.name) initial[c.name] = Boolean(c.enabled);
    }
    setCapabilityState(initial);
  }, [settingsOpened, line.name, line.capabilities, line.number]);

  const changeAgent = (slug: string) => {
    updateWhatsappNumber(number, { slug }).then(() => {
      toast.success(t("whatsapp-agent-changed"));
      void onRefresh();
    });
  };

  const updateName = () => {
    updateWhatsappNumber(number, { name: nameInput }).then(() => {
      toast.success(t("whatsapp-name-updated"));
      void onRefresh();
    });
  };

  const saveCapabilities = () => {
    const capabilities = buildCapabilitiesPayload(capabilityState);
    updateWhatsappNumber(number, { capabilities }).then(() => {
      toast.success(t("whatsapp-capabilities-saved"));
      void onRefresh();
    });
  };

  return (
    <>
      <Card
        withBorder
        padding="lg"
        style={{ cursor: "pointer" }}
        onClick={openSettings}
      >
        <Title order={4} ta="center">
          {name || number}
        </Title>
        <Text ta="center" size="lg">
          📞 {number}
        </Text>
        <Group justify="center" gap="md" mt="xs">
          <Text size="sm">🧠 {agent.name}</Text>
          <Text size="sm">💬 {conversations_count}</Text>
        </Group>
      </Card>

      <Modal
        opened={settingsOpened}
        onClose={closeSettings}
        title={t("whatsapp-settings-title")}
        centered
        size="lg"
      >
        <Stack gap="md">
          <Group gap="sm" align="flex-end">
            <TextInput
              label={t("whatsapp-display-name")}
              value={nameInput}
              onChange={(e) => {
                const val = e.currentTarget.value;
                setNameInput(val);
              }}
              style={{ flex: 1 }}
            />
            <Button
              leftSection={<IconDeviceFloppy size={16} />}
              onClick={updateName}
            >
              {t("whatsapp-update-name")}
            </Button>
          </Group>

          <div>
            <Text size="sm" fw={500} mb={4}>
              {t("whatsapp-change-agent")}
            </Text>
            <AgentSelector
              onSelectAgent={changeAgent}
              selectedSlug={agent.slug}
            />
          </div>

          <div>
            <Text size="sm" fw={500} mb="xs">
              {t("whatsapp-capabilities")}
            </Text>
            <Stack gap="sm">
              {WHATSAPP_CAPABILITY_NAMES.map((capName) => (
                <Stack key={capName} gap={2}>
                  <Checkbox
                    label={t(`widget-capability-${capName}-title`)}
                    checked={capabilityState[capName] ?? false}
                    onChange={(e) => {
                      const checked = e.currentTarget.checked;
                      setCapabilityState((prev) => ({
                        ...prev,
                        [capName]: checked,
                      }));
                    }}
                  />
                  <Text size="xs" c="dimmed" ml={28}>
                    {t(`widget-capability-${capName}-description`)}
                  </Text>
                </Stack>
              ))}
            </Stack>
            <Button
              mt="sm"
              leftSection={<IconDeviceFloppy size={16} />}
              variant="default"
              onClick={saveCapabilities}
            >
              {t("whatsapp-save-capabilities")}
            </Button>
          </div>

          <Title order={5}>{t("whatsapp-conversations")}</Title>
          <Stack gap="sm">
            {conversations.map((conversation) => (
              <ConversationComponent key={conversation.id} {...conversation} />
            ))}
          </Stack>
        </Stack>
      </Modal>
    </>
  );
};

const ConversationComponent = ({
  title,
  whatsapp_user_number,
  id,
  summary,
}: {
  title: string | null;
  whatsapp_user_number: string | null;
  id: string;
  summary: string | null;
}) => {
  const [messages, setMessages] = useState<any[]>([]);
  const [showMessages, setShowMessages] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const [messageInput, setMessageInput] = useState("");

  const getMessages = () => {
    getWhatsappConversationMessages(id).then((res) => {
      setMessages((res as any).messages);
      setShowMessages(true);
    });
  };

  const sendMessage = () => {
    if (messageInput.trim() === "") return;
    sendMessageToConversation(id, messageInput).then(() => {
      setMessageInput("");
    });
  };

  return (
    <>
      <Card
        withBorder
        padding="md"
        style={{ cursor: "pointer" }}
        onClick={getMessages}
      >
        <Title order={5}>{title}</Title>
        <Text size="sm">{whatsapp_user_number || "—"}</Text>
      </Card>

      <Modal
        opened={showMessages}
        onClose={() => setShowMessages(false)}
        title={title || "No title"}
        centered
        size="lg"
      >
        <Stack gap="md">
          <Card withBorder p="sm" className="whatsapp-header">
            <Text size="sm">
              {summary ? (
                showMore ? (
                  summary
                ) : (
                  summary.slice(0, 80) + "..."
                )
              ) : (
                "No summary"
              )}
            </Text>
            <Button
              variant="subtle"
              size="xs"
              onClick={() => setShowMore(!showMore)}
              mt={4}
            >
              {showMore ? "Hide" : "Read more →"}
            </Button>
          </Card>

          <div className="whatsapp-messages">
            {messages &&
              messages.map((message) => (
                <WhatsAppMessage key={message.id} {...message} />
              ))}
          </div>

          <Group gap="sm" align="flex-end">
            <Textarea
              value={messageInput}
              onChange={(e) => {
                const val = e.currentTarget.value;
                setMessageInput(val);
              }}
              placeholder="Write a message"
              autosize
              minRows={1}
              maxRows={4}
              style={{ flex: 1 }}
            />
            <ActionIcon size="lg" onClick={sendMessage}>
              <IconSend size={18} />
            </ActionIcon>
          </Group>
        </Stack>
      </Modal>
    </>
  );
};

const WhatsAppMessage = ({
  text,
  type,
  created_at,
  metadata,
}: {
  text: string;
  type: string;
  created_at: string;
  metadata?: { whatsapp_reaction?: string } | null;
}) => {
  const reaction = metadata?.whatsapp_reaction;
  const date = new Date(created_at);
  const formattedDate = date.toLocaleString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  });

  return (
    <div
      className={`text-center d-flex flex-y message ${type.toLowerCase()}`}
    >
      <div className="text-left message-text">
        <MarkdownRenderer markdown={text} />
        {reaction && <span className="reaction">{reaction} ✔️✔️</span>}
      </div>
      <Text size="xs" c="dimmed" p="xs">
        {formattedDate}
      </Text>
    </div>
  );
};
