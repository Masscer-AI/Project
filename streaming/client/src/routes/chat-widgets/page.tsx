import React, { useEffect, useState } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import {
  getChatWidgets,
  createChatWidget,
  updateChatWidget,
  deleteChatWidget,
} from "../../modules/apiCalls";
import { TChatWidget } from "../../types";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";

import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Checkbox,
  ColorInput,
  CopyButton,
  Group,
  Loader,
  NativeSelect,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import {
  IconCheck,
  IconCode,
  IconCopy,
  IconEdit,
  IconMenu2,
  IconPencil,
  IconPlus,
  IconPuzzle,
  IconTrash,
  IconX,
} from "@tabler/icons-react";

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ChatWidgetsPage() {
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));

  const { t } = useTranslation();

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
            <ActionIcon
              variant="subtle"
              color="gray"
              onClick={toggleSidebar}
            >
              <IconMenu2 size={20} />
            </ActionIcon>
          </Box>
        )}

        <Box px="md" w="100%" maw="52rem" mx="auto">
          <Title order={2} ta="center" mb="xs" mt="md">
            {t("chat-widgets")}
          </Title>
          <Text ta="center" c="dimmed" mb="lg" size="sm">
            {t("widget-manager-description")}
          </Text>

          <WidgetList />
        </Box>
      </div>
    </main>
  );
}

// ─── Widget List ──────────────────────────────────────────────────────────────

const WidgetList = () => {
  const { t } = useTranslation();
  const { agents, fetchAgents } = useStore((s) => ({
    agents: s.agents,
    fetchAgents: s.fetchAgents,
  }));

  const [widgets, setWidgets] = useState<TChatWidget[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);

  useEffect(() => {
    loadWidgets();
    if (agents.length === 0) {
      fetchAgents();
    }
  }, []);

  const loadWidgets = async () => {
    try {
      setIsLoading(true);
      const data = await getChatWidgets();
      setWidgets(data);
    } catch {
      toast.error(t("error-loading-widgets"));
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (widgetId: number) => {
    try {
      await deleteChatWidget(widgetId);
      setWidgets((prev) => prev.filter((w) => w.id !== widgetId));
      toast.success(t("widget-deleted"));
    } catch {
      toast.error(t("error-deleting-widget"));
    }
  };

  return (
    <Stack gap="md">
      {!showCreateForm && (
        <Group justify="flex-end">
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => {
              setShowCreateForm(true);
              setEditingId(null);
            }}
          >
            {t("new-widget")}
          </Button>
        </Group>
      )}

      {showCreateForm && (
        <WidgetForm
          agents={agents}
          onSave={async (data) => {
            try {
              const newWidget = await createChatWidget(data);
              setWidgets((prev) => [newWidget, ...prev]);
              setShowCreateForm(false);
              toast.success(t("widget-created"));
            } catch {
              toast.error(t("error-creating-widget"));
            }
          }}
          onCancel={() => setShowCreateForm(false)}
        />
      )}

      {isLoading ? (
        <Stack align="center" py="xl">
          <Loader color="violet" />
        </Stack>
      ) : widgets.length === 0 && !showCreateForm ? (
        <Card withBorder p="xl">
          <Stack align="center" gap="sm" py="lg">
            <IconPuzzle size={40} opacity={0.3} />
            <Text c="dimmed">{t("no-widgets-found")}</Text>
            <Button
              variant="light"
              leftSection={<IconPlus size={16} />}
              onClick={() => setShowCreateForm(true)}
            >
              {t("new-widget")}
            </Button>
          </Stack>
        </Card>
      ) : (
        widgets.map((widget) =>
          editingId === widget.id ? (
            <WidgetForm
              key={widget.id}
              agents={agents}
              initialData={widget}
              onSave={async (data) => {
                try {
                  const updated = await updateChatWidget(widget.id, data);
                  setWidgets((prev) =>
                    prev.map((w) => (w.id === updated.id ? updated : w))
                  );
                  setEditingId(null);
                  toast.success(t("widget-updated"));
                } catch {
                  toast.error(t("error-updating-widget"));
                }
              }}
              onCancel={() => setEditingId(null)}
            />
          ) : (
            <WidgetCard
              key={widget.id}
              widget={widget}
              onEdit={() => {
                setEditingId(widget.id);
                setShowCreateForm(false);
              }}
              onDelete={handleDelete}
            />
          )
        )
      )}
    </Stack>
  );
};

// ─── Widget Form ──────────────────────────────────────────────────────────────

interface WidgetFormData {
  name: string;
  agent_id: number | null;
  enabled: boolean;
  avatar_image: string;
  first_message: string;
  capabilities: { name: string; type: "internal_tool"; enabled: boolean }[];
  style?: {
    primary_color?: string;
    theme?: "default" | "light" | "dark";
    show_history?: boolean;
  };
}

type WidgetTheme = "default" | "light" | "dark";
const DEFAULT_CAPABILITY_NAMES = [
  "read_attachment",
  "list_attachments",
  "explore_web",
  "rag_query",
  "create_image",
  "create_speech",
  "read_plugin_instructions",
  "raise_alert",
];

const WidgetForm = ({
  agents,
  initialData,
  onSave,
  onCancel,
}: {
  agents: { id?: number; name: string; slug: string }[];
  initialData?: TChatWidget;
  onSave: (data: WidgetFormData) => Promise<void>;
  onCancel: () => void;
}) => {
  const { t } = useTranslation();
  const [saving, setSaving] = useState(false);

  const matchedAgent = initialData
    ? agents.find((a) => a.slug === initialData.agent_slug)
    : null;

  const [name, setName] = useState(initialData?.name || "");
  const [agentId, setAgentId] = useState<string>(
    matchedAgent ? String(matchedAgent.id) : ""
  );
  const [enabled, setEnabled] = useState(initialData?.enabled ?? true);
  const [avatarImage, setAvatarImage] = useState(initialData?.avatar_image ?? "");
  const [firstMessage, setFirstMessage] = useState(initialData?.first_message ?? "");
  const [primaryColor, setPrimaryColor] = useState(
    initialData?.style?.primary_color ?? ""
  );
  const [theme, setTheme] = useState<WidgetTheme>(
    initialData?.style?.theme ?? "default"
  );
  const [showHistory, setShowHistory] = useState(
    initialData?.style?.show_history === true
  );
  const [capabilityState, setCapabilityState] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    for (const name of DEFAULT_CAPABILITY_NAMES) initial[name] = false;
    for (const capability of initialData?.capabilities ?? []) {
      if (!capability?.name) continue;
      initial[capability.name] = Boolean(capability.enabled);
    }
    return initial;
  });

  const handleSubmit = async () => {
    if (!name.trim()) {
      toast.error(t("widget-name-required"));
      return;
    }
    const trimmedPrimaryColor = primaryColor.trim();
    if (
      trimmedPrimaryColor &&
      !/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(trimmedPrimaryColor)
    ) {
      toast.error(t("widget-primary-color-invalid"));
      return;
    }
    setSaving(true);
    try {
      const stylePayload: {
        primary_color?: string;
        theme?: WidgetTheme;
        show_history: boolean;
      } = {
        theme,
        show_history: showHistory,
      };
      if (trimmedPrimaryColor) {
        stylePayload.primary_color = trimmedPrimaryColor;
      }
      await onSave({
        name: name.trim(),
        agent_id: agentId ? parseInt(agentId) : null,
        enabled,
        avatar_image: avatarImage.trim(),
        first_message: firstMessage.trim(),
        capabilities: Object.entries(capabilityState).map(([name, isEnabled]) => ({
          name,
          type: "internal_tool",
          enabled: isEnabled,
        })),
        style: stylePayload,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card withBorder p="lg">
      <Title order={4} mb="md">
        {initialData ? t("edit-widget") : t("create-widget")}
      </Title>

      <Stack gap="sm">
        <TextInput
          label={t("name")}
          placeholder={t("widget-name-placeholder")}
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
          required
        />

        <NativeSelect
          label={t("agent")}
          value={agentId}
          onChange={(e) => setAgentId(e.currentTarget.value)}
          data={[
            { value: "", label: t("select-agent") },
            ...agents.map((a) => ({
              value: String(a.id),
              label: a.name,
            })),
          ]}
        />

        <TextInput
          label={t("widget-avatar-image")}
          description={t("widget-avatar-image-description")}
          placeholder={t("widget-avatar-image-placeholder")}
          value={avatarImage}
          onChange={(e) => setAvatarImage(e.currentTarget.value)}
          type="text"
        />

        <Textarea
          label={t("widget-first-message")}
          description={t("widget-first-message-description")}
          placeholder={t("widget-first-message-placeholder")}
          value={firstMessage}
          onChange={(e) => setFirstMessage(e.currentTarget.value)}
          autosize
          minRows={2}
          maxRows={4}
        />

        <ColorInput
          label={t("widget-primary-color")}
          description={t("widget-primary-color-description")}
          placeholder="#667eea"
          value={primaryColor}
          format="hex"
          withPicker
          swatches={[
            "#000000",
            "#667eea",
            "#7c3aed",
            "#0ea5e9",
            "#10b981",
            "#f59e0b",
            "#ef4444",
            "#ec4899",
          ]}
          onChange={setPrimaryColor}
          __clearable={true}
        />

        <NativeSelect
          label={t("widget-theme")}
          description={t("widget-theme-description")}
          value={theme}
          onChange={(e) => setTheme(e.currentTarget.value as WidgetTheme)}
          data={[
            { value: "default", label: t("widget-theme-default") },
            { value: "light", label: t("widget-theme-light") },
            { value: "dark", label: t("widget-theme-dark") },
          ]}
        />

        <Group gap="lg" mt="xs">
          <Checkbox
            label={t("enabled")}
            checked={enabled}
            onChange={(e) => setEnabled(e.currentTarget.checked)}
          />
        </Group>

        <Stack gap={6} mt="xs">
          <Text size="sm" fw={500}>
            {t("widget-capabilities")}
          </Text>
          <Stack gap={2}>
            <Checkbox
              label={t("widget-show-history")}
              checked={showHistory}
              onChange={(e) => setShowHistory(e.currentTarget.checked)}
            />
            <Text size="xs" c="dimmed" ml={28}>
              {t("widget-show-history-description")}
            </Text>
          </Stack>
          {Object.keys(capabilityState)
            .sort()
            .map((capabilityName) => (
              <Stack key={capabilityName} gap={2}>
                <Checkbox
                  label={t(`widget-capability-${capabilityName}-title`)}
                  checked={capabilityState[capabilityName]}
                  onChange={(e) => {
                    const checked = e.currentTarget.checked;
                    setCapabilityState((prev) => ({
                      ...prev,
                      [capabilityName]: checked,
                    }));
                  }}
                />
                <Text size="xs" c="dimmed" ml={28}>
                  {t(`widget-capability-${capabilityName}-description`)}
                </Text>
              </Stack>
            ))}
        </Stack>

        <Group justify="flex-end" mt="sm">
          <Button variant="default" onClick={onCancel}>
            {t("cancel")}
          </Button>
          <Button onClick={handleSubmit} loading={saving}>
            {initialData ? t("update") : t("create")}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
};

// ─── Widget Card ──────────────────────────────────────────────────────────────

const WidgetCard = ({
  widget,
  onEdit,
  onDelete,
}: {
  widget: TChatWidget;
  onEdit: () => void;
  onDelete: (id: number) => void;
}) => {
  const { t } = useTranslation();
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <Card withBorder p="md">
      <Group justify="space-between" wrap="nowrap" mb="xs">
        <Group gap="sm">
          <Text fw={600}>{widget.name}</Text>
          <Badge
            size="sm"
            color={widget.enabled ? "green" : "red"}
            variant="light"
          >
            {widget.enabled ? t("enabled") : t("disabled")}
          </Badge>
        </Group>

        <Group gap={4}>
          <Tooltip label={t("edit")}>
            <ActionIcon variant="default" size="sm" onClick={onEdit}>
              <IconPencil size={14} />
            </ActionIcon>
          </Tooltip>
          <Button
            variant="light"
            color={confirmDelete ? "red" : "gray"}
            size="compact-xs"
            leftSection={<IconTrash size={14} />}
            onClick={() => {
              if (confirmDelete) {
                onDelete(widget.id);
                setConfirmDelete(false);
              } else {
                setConfirmDelete(true);
              }
            }}
            onBlur={() => setConfirmDelete(false)}
          >
            {confirmDelete ? t("im-sure") : t("delete")}
          </Button>
        </Group>
      </Group>

      {widget.agent_name && (
        <Text size="sm" c="dimmed" mb="xs">
          {t("agent")}: <Text span fw={500} c="white">{widget.agent_name}</Text>
        </Text>
      )}

      {widget.avatar_image && (
        <Text size="sm" c="dimmed" mb="xs">
          {t("widget-avatar-image")}:{" "}
          <Text span fw={500}>
            {widget.avatar_image}
          </Text>
        </Text>
      )}

      {widget.first_message && (
        <Text size="sm" c="dimmed" mb="xs">
          {t("widget-first-message")}:{" "}
          <Text span fw={500} c="white">
            {widget.first_message}
          </Text>
        </Text>
      )}

      <Group gap={6} mb="sm">
        {widget.style?.theme && (
          <Badge size="xs" variant="light" color="indigo">
            {t("widget-theme")}: {t(`widget-theme-${widget.style.theme}`)}
          </Badge>
        )}
        {widget.style?.primary_color && (
          <Badge size="xs" variant="light" color="gray">
            {t("widget-primary-color")}: {widget.style.primary_color}
          </Badge>
        )}
        {widget.style?.show_history && (
          <Badge size="xs" variant="light" color="teal">
            {t("widget-show-history")}
          </Badge>
        )}
        {widget.capabilities
          ?.filter((capability) => capability.enabled)
          .map((capability) => (
            <Badge key={capability.name} size="xs" variant="light" color="blue">
              {capability.name}
            </Badge>
          ))}
      </Group>

      {/* Embed code - use window.location.origin so it reflects current host when FRONTEND_URL not set */}
      <Group gap="xs" wrap="nowrap">
        {(() => {
          const origin =
            typeof window !== "undefined" ? window.location.origin : "";
          const embedCode = `<script src="${origin}/widget/${widget.token}.js"></script>`;
          return (
            <>
              <TextInput
                value={embedCode}
                readOnly
                size="xs"
                leftSection={<IconCode size={14} />}
                style={{ flex: 1 }}
                styles={{
                  input: { fontFamily: "monospace", fontSize: 12 },
                }}
              />
              <CopyButton value={embedCode}>
                {({ copied, copy }) => (
                  <Tooltip label={copied ? t("copied") : t("copy")}>
                    <ActionIcon
                      variant={copied ? "filled" : "default"}
                      color={copied ? "teal" : undefined}
                      size="sm"
                      onClick={copy}
                    >
                      {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                    </ActionIcon>
                  </Tooltip>
                )}
              </CopyButton>
            </>
          );
        })()}
      </Group>
    </Card>
  );
};
