import React, { useRef, useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { v4 as uuidv4 } from "uuid";
import { useStore } from "../../modules/store";
import toast from "react-hot-toast";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import { useTranslation } from "react-i18next";
import { generateDocumentBrief, getDocuments } from "../../modules/apiCalls";
import { SpeechHandler } from "../SpeechHandler/SpeechHandler";
import { WebsiteFetcher } from "../WebsiteFetcher/WebsiteFetcher";
import { TAttachment, TDocument } from "../../types";
import { SYSTEM_PLUGINS } from "../../modules/plugins";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import "./ChatInput.css";

import {
  Modal,
  Button,
  ActionIcon,
  Switch,
  NumberInput,
  Stack,
  Group,
  Text,
  Title,
  Card,
  Divider,
  Indicator,
  Menu,
  Textarea as MantineTextarea,
  Loader as MantineLoader,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconSend,
  IconPencil,
  IconFileText,
  IconGlobe,
  IconPuzzle,
  IconSettings,
  IconPlus,
  IconFilePlus,
  IconLink,
  IconTree,
  IconUsers,
  IconAdjustments,
} from "@tabler/icons-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ChatInputProps {
  handleSendMessage: (input: string) => Promise<boolean>;
  initialInput: string;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const allowedDocumentTypes = [
  "application/pdf",
  "text/plain",
  "text/html",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];

const allowedImageTypes = [
  "image/png",
  "image/jpeg",
  "image/gif",
  "image/webp",
];

const getCommand = (text: string): string | null => {
  const regex = /k\/(.*)$/;
  const match = text.match(regex);
  return match ? match[1] : null;
};

// ─── Main ChatInput ──────────────────────────────────────────────────────────

export const ChatInput: React.FC<ChatInputProps> = ({
  handleSendMessage,
  initialInput,
}) => {
  const { t } = useTranslation();
  const {
    attachments,
    addAttachment,
    chatState,
    toggleWritingMode,
  } = useStore((state) => ({
    attachments: state.chatState.attachments,
    addAttachment: state.addAttachment,
    chatState: state.chatState,
    toggleWritingMode: state.toggleWrittingMode,
  }));

  const [textPrompt, setTextPrompt] = useState(initialInput);
  const isTranscribeEnabled = useIsFeatureEnabled("transcribe-on-chat");

  useEffect(() => {
    setTextPrompt(initialInput);
  }, [initialInput]);

  useEffect(() => {
    const command = getCommand(textPrompt);
    if (command) {
      console.log(command);
    }
  }, [textPrompt]);

  const handlePaste = (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = event.clipboardData.items;
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (allowedImageTypes.includes(item.type)) {
        const blob = item.getAsFile();
        const reader = new FileReader();

        reader.onload = (event) => {
          const target = event.target;
          if (!target) return;
          const result = target.result;
          if (!result) return;
          const id = uuidv4();

          if (!blob) return;

          addAttachment({
            content: result as string,
            type: "image",
            name: id,
            file: blob,
            text: "",
          });
        };
        if (blob) reader.readAsDataURL(blob);
      }
    }
  };

  const handleAudioTranscript = (
    transcript: string,
    audioUrl: string,
    base64Audio: string
  ) => {
    setTextPrompt((prev) => prev + " " + transcript);
  };

  const handleKeyDown = async (
    event: React.KeyboardEvent<HTMLTextAreaElement>
  ) => {
    if (event.key === "Enter" && event.shiftKey) return;
    if (event.key === "Enter" && chatState.writtingMode) return;
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      const result = await handleSendMessage(textPrompt);
      if (result) setTextPrompt("");
    }
  };

  const asyncSendMessage = async () => {
    const result = await handleSendMessage(textPrompt);
    if (result) setTextPrompt("");
  };

  useHotkeys("ctrl+alt+w", () => toggleWritingMode(), {
    enableOnFormTags: true,
  });

  return (
    <div className="flex flex-col justify-center items-center p-0 w-full max-w-[900px] bg-transparent z-[2] gap-0 mt-4 overflow-visible">
      <section className="chat-input-attachments flex gap-2.5 flex-nowrap overflow-x-auto empty:hidden w-full mb-3 px-4 [scrollbar-width:thin] [scrollbar-color:rgba(128,128,128,0.3)_transparent] [&::-webkit-scrollbar]:h-1 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-[rgba(128,128,128,0.3)] [&::-webkit-scrollbar-thumb]:rounded-full">
        {attachments.map((a, index) => (
          <Thumbnail
            {...a}
            key={index}
            src={a.content}
            index={index}
            showFloatingButtons={true}
            mode={a.mode}
          />
        ))}
      </section>
      <section className="flex-1 w-full flex flex-col items-center justify-center relative overflow-visible">
        <div className="w-full rounded-none md:rounded-2xl overflow-visible relative" style={{ background: "var(--bg-contrast-color)", border: "1px solid var(--hovered-color)" }}>
          <MantineTextarea
            autosize
            minRows={chatState.writtingMode ? 8 : 1}
            maxRows={chatState.writtingMode ? 20 : 3}
            classNames={{
              input: "!bg-transparent !border-0 !text-sm !font-sans focus:!ring-0 focus:!outline-none !px-3 md:!px-5 !py-2 md:!py-3",
              wrapper: "!bg-transparent",
              root: "!bg-transparent",
            }}
            styles={{
              input: {
                color: "var(--font-color)",
              },
            }}
            value={textPrompt}
            onChange={(e) => setTextPrompt(e.currentTarget.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={t("type-your-message")}
            name="chat-input"
            variant="unstyled"
          />
          <div className="flex items-center justify-between px-1 md:px-4 pb-1 md:pb-4 pt-1 md:pt-3 relative z-10 min-w-0">
            <div className="flex gap-2 relative z-20 min-w-0 flex-shrink">
              <PlusMenu />
              <ToolsMenu />
            </div>
            <div className="flex gap-2 items-center flex-shrink-0">
              {isTranscribeEnabled && (
                <SpeechHandler onTranscript={handleAudioTranscript} />
              )}
              <ActionIcon
                onClick={asyncSendMessage}
                variant="subtle"
                color="gray"
                size="lg"
                radius="xl"
                aria-label={t("send-message")}
              >
                <IconSend size={18} />
              </ActionIcon>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

// ─── Plus Menu (+) ───────────────────────────────────────────────────────────

const PlusMenu = () => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const addAttachment = useStore((s) => s.addAttachment);
  const attachments = useStore((s) => s.chatState.attachments);
  const isAddFilesEnabled = useIsFeatureEnabled("add-files-to-chat");
  const isTrainAgentsEnabled = useIsFeatureEnabled("train-agents");
  const isWebScrapingEnabled = useIsFeatureEnabled("web-scraping");

  const [ragConfigOpened, { open: openRagConfig, close: closeRagConfig }] =
    useDisclosure(false);
  const [websiteFetcherOpen, setWebsiteFetcherOpen] = useState(false);

  const hasAttachments = attachments.length > 0;

  const addDocument = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files) return;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (
        allowedImageTypes.includes(file.type) ||
        allowedDocumentTypes.includes(file.type)
      ) {
        const reader = new FileReader();
        reader.onload = (event) => {
          const target = event.target;
          if (!target) return;
          const result = target.result;
          if (!result) return;
          addAttachment({
            content: result as string,
            file: file,
            type: file.type,
            name: file.name,
            text: "",
          });
        };
        reader.readAsDataURL(file);
      } else {
        toast.error(t("file-type-not-allowed"));
      }
    }
    // Reset input so the same file can be selected again
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const hasAnyPlusOption = isAddFilesEnabled || isTrainAgentsEnabled || isWebScrapingEnabled;

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        onChange={addDocument}
        style={{ display: "none" }}
        accept=".png,.jpeg,.jpg,.gif,.webp,.pdf,.txt,.html,.doc,.docx"
      />

      {hasAnyPlusOption && (
      <Menu shadow="md" width={220} position="top-start" withArrow>
        <Menu.Target>
          <Indicator
            disabled={!hasAttachments}
            processing
            color="violet"
            size={8}
          >
            <ActionIcon variant="subtle" color="gray" size="lg">
              <IconPlus size={20} />
            </ActionIcon>
          </Indicator>
        </Menu.Target>
        <Menu.Dropdown>
          {isAddFilesEnabled && (
            <Menu.Item
              leftSection={<IconFilePlus size={18} />}
              onClick={() => fileInputRef.current?.click()}
            >
              {t("add-files")}
            </Menu.Item>
          )}
          {isTrainAgentsEnabled && (
            <Menu.Item
              leftSection={<IconFileText size={18} />}
              onClick={openRagConfig}
            >
              {t("add-existing-documents")}
            </Menu.Item>
          )}
          {isWebScrapingEnabled && (
            <Menu.Item
              leftSection={<IconLink size={18} />}
              onClick={() => setWebsiteFetcherOpen(true)}
            >
              {t("fetch-urls") || "Fetch URLs"}
            </Menu.Item>
          )}
        </Menu.Dropdown>
      </Menu>
      )}

      <RagConfig opened={ragConfigOpened} onClose={closeRagConfig} />
      <WebsiteFetcher
        isOpen={websiteFetcherOpen}
        onClose={() => setWebsiteFetcherOpen(false)}
      />
    </>
  );
};

// ─── Tools Menu ──────────────────────────────────────────────────────────────

const ToolsMenu = () => {
  const { t } = useTranslation();
  const isTrainAgentsEnabled = useIsFeatureEnabled("train-agents");
  const isWebScrapingEnabled = useIsFeatureEnabled("web-scraping");
  const {
    chatState,
    toggleUseRag,
    toggleWebSearch,
    toggleWritingMode,
  } = useStore((state) => ({
    chatState: state.chatState,
    toggleUseRag: state.toggleUseRag,
    toggleWebSearch: state.toggleWebSearch,
    toggleWritingMode: state.toggleWrittingMode,
  }));

  const [pluginsOpened, { open: openPlugins, close: closePlugins }] =
    useDisclosure(false);
  const [settingsOpened, { open: openSettings, close: closeSettings }] =
    useDisclosure(false);

  const hasActiveTools =
    chatState.useRag ||
    chatState.webSearch ||
    (chatState.specifiedUrls?.length ?? 0) > 0 ||
    chatState.selectedPlugins.length > 0 ||
    chatState.writtingMode;

  return (
    <>
      <Menu
        shadow="md"
        width={260}
        position="top-start"
        withArrow
        closeOnItemClick={false}
      >
        <Menu.Target>
          <Indicator
            disabled={!hasActiveTools}
            processing
            color="violet"
            size={8}
          >
            <ActionIcon variant="subtle" color="gray" size="lg">
              <IconAdjustments size={20} />
            </ActionIcon>
          </Indicator>
        </Menu.Target>
        <Menu.Dropdown>
          {isTrainAgentsEnabled && (
            <Menu.Item
              leftSection={<IconFileText size={18} />}
              rightSection={
                <Switch
                  checked={chatState.useRag}
                  onChange={() => toggleUseRag()}
                  color="violet"
                  size="xs"
                  styles={{ track: { cursor: "pointer" } }}
                />
              }
              onClick={() => toggleUseRag()}
            >
              RAG
            </Menu.Item>
          )}
          {isWebScrapingEnabled && (
            <Menu.Item
              leftSection={<IconGlobe size={18} />}
              rightSection={
                <Switch
                  checked={chatState.webSearch}
                  onChange={() => toggleWebSearch()}
                  color="violet"
                  size="xs"
                  styles={{ track: { cursor: "pointer" } }}
                />
              }
              onClick={() => toggleWebSearch()}
            >
              {t("auto-search") || "Web Search"}
            </Menu.Item>
          )}
          <Menu.Item
            leftSection={<IconPencil size={18} />}
            rightSection={
              <Switch
                checked={chatState.writtingMode}
                onChange={() => toggleWritingMode()}
                color="violet"
                size="xs"
                styles={{ track: { cursor: "pointer" } }}
              />
            }
            onClick={() => toggleWritingMode()}
          >
            {t("turn-on-off-writing-mode") || "Writing mode"}
          </Menu.Item>

          <Menu.Divider />

          <Menu.Item
            leftSection={<IconPuzzle size={18} />}
            onClick={openPlugins}
            closeMenuOnClick
            rightSection={
              chatState.selectedPlugins.length > 0 ? (
                <Text size="xs" c="violet">
                  {chatState.selectedPlugins.length}
                </Text>
              ) : null
            }
          >
            {t("plugin-selector") || "Plugins"}
          </Menu.Item>
          <Menu.Item
            leftSection={<IconSettings size={18} />}
            onClick={openSettings}
            closeMenuOnClick
          >
            {t("conversation-settings") || "Settings"}
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>

      <PluginSelectorModal opened={pluginsOpened} onClose={closePlugins} />
      <ConversationConfigModal
        opened={settingsOpened}
        onClose={closeSettings}
      />
    </>
  );
};

// ─── FileLoader (exported for use elsewhere) ─────────────────────────────────

export const FileLoader = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { t } = useTranslation();
  const addAttachment = useStore((s) => s.addAttachment);

  const addDocument = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files) return;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (
        allowedImageTypes.includes(file.type) ||
        allowedDocumentTypes.includes(file.type)
      ) {
        const reader = new FileReader();
        reader.onload = (event) => {
          const target = event.target;
          if (!target) return;
          const result = target.result;
          if (!result) return;
          addAttachment({
            content: result as string,
            file: file,
            type: file.type,
            name: file.name,
            text: "",
          });
        };
        reader.readAsDataURL(file);
      } else {
        toast.error(t("file-type-not-allowed"));
      }
    }
  };

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        onChange={addDocument}
        style={{ display: "none" }}
        id="fileInput"
        accept=".png,.jpeg,.jpg,.gif,.webp,.pdf,.txt,.html,.doc,.docx"
      />
      <label htmlFor="fileInput">
        <Button
          component="span"
          onClick={() => fileInputRef.current?.click()}
          leftSection={<IconFilePlus size={18} />}
          variant="light"
          fullWidth
        >
          {t("add-files")}
        </Button>
      </label>
    </>
  );
};

// ─── RagConfig Modal ─────────────────────────────────────────────────────────

const RagConfig = ({
  opened,
  onClose,
}: {
  opened: boolean;
  onClose: () => void;
}) => {
  const [documents, setDocuments] = useState([] as TDocument[]);
  const [isLoading, setIsLoading] = useState(false);

  const { t } = useTranslation();

  useEffect(() => {
    if (opened) getDocs();
  }, [opened]);

  const getDocs = async () => {
    setIsLoading(true);
    const docs = await getDocuments();
    setDocuments(docs);
    setIsLoading(false);
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={<Title order={4}>{t("select-documents-to-use")}</Title>}
      size="lg"
      centered
      overlayProps={{ backgroundOpacity: 0.55, blur: 3 }}
    >
      <Group gap="sm" justify="center">
        {isLoading && (
          <Stack align="center" py="xl">
            <MantineLoader />
            <Text size="sm" c="dimmed">
              {t("loading-documents")}
            </Text>
          </Stack>
        )}
        {!isLoading &&
          documents.map((d) => <DocumentCard d={d} key={d.id} />)}
        {!isLoading && documents.length === 0 && (
          <Text c="dimmed" py="xl">
            {t("no-documents-found")}
          </Text>
        )}
      </Group>
    </Modal>
  );
};

// ─── DocumentCard ────────────────────────────────────────────────────────────

const DocumentCard = ({ d }: { d: TDocument }) => {
  const { addAttatchment, chatState, removeAttatchment } = useStore((s) => ({
    addAttatchment: s.addAttachment,
    chatState: s.chatState,
    removeAttatchment: s.deleteAttachment,
  }));

  const { t } = useTranslation();
  const isAttached =
    chatState.attachments.findIndex((a) => a.id == d.id) !== -1;

  const toggleDocument = (d: TDocument) => {
    if (!isAttached) {
      const attachment: TAttachment = {
        content: d.text,
        name: d.name,
        type: "text/plain",
        id: d.id,
        mode: "all_possible_text",
        text: d.text,
      };
      addAttatchment(attachment, true);
    } else {
      removeAttatchment(
        chatState.attachments.findIndex((a) => a.id == d.id)
      );
    }
  };

  const generateBrief = async () => {
    toast.success(t("generating-brief"));
    await generateDocumentBrief(String(d.id));
  };

  return (
    <Card
      shadow="sm"
      padding="sm"
      radius="md"
      withBorder
      style={{
        backgroundColor: isAttached
          ? "var(--mantine-color-violet-light)"
          : undefined,
        borderColor: isAttached
          ? "var(--mantine-color-violet-6)"
          : undefined,
        cursor: "pointer",
      }}
    >
      <Text fw={500} mb="xs">
        {d.name}
      </Text>
      {d.brief && (
        <Text size="sm" c="dimmed" title={d.brief} mb="xs">
          {d.brief.slice(0, 200)}...
        </Text>
      )}
      <Group gap="xs">
        <Button
          onClick={() => toggleDocument(d)}
          leftSection={<IconPlus size={16} />}
          variant={isAttached ? "filled" : "light"}
          color={isAttached ? "violet" : "gray"}
          size="xs"
        >
          {isAttached ? t("remove-document") : t("add-document")}
        </Button>
        {!d.brief && (
          <Button
            onClick={generateBrief}
            leftSection={<IconPlus size={16} />}
            variant="light"
            size="xs"
          >
            {t("generate-brief")}
          </Button>
        )}
      </Group>
    </Card>
  );
};

// ─── ConversationConfig Modal ────────────────────────────────────────────────

const ConversationConfigModal = ({
  opened,
  onClose,
}: {
  opened: boolean;
  onClose: () => void;
}) => {
  const { userPreferences, setPreferences } = useStore((s) => ({
    userPreferences: s.userPreferences,
    setPreferences: s.setPreferences,
  }));
  const { t } = useTranslation();
  const isChatSpeechEnabled = useIsFeatureEnabled("chat-generate-speech");

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={<Title order={4}>{t("conversation-settings")}</Title>}
      size="lg"
      centered
      overlayProps={{ backgroundOpacity: 0.55, blur: 3 }}
    >
      <Stack gap="md">
        <div>
          <Text fw={500} mb={4}>
            {t("max-memory-messages")}
          </Text>
          <Text size="sm" c="dimmed" mb="xs">
            {t("max-memory-messages-description")}
          </Text>
          <NumberInput
            value={userPreferences.max_memory_messages}
            onChange={(val) =>
              setPreferences({
                max_memory_messages: typeof val === "number" ? val : 0,
              })
            }
            min={0}
          />
        </div>

        {isChatSpeechEnabled && (
          <>
            <Divider />

            <Group justify="space-between">
              <div>
                <Text fw={500}>{t("auto-play")}</Text>
                <Text size="sm" c="dimmed">
                  {t("auto-play-description")}
                </Text>
              </div>
              <Switch
                checked={userPreferences.autoplay}
                onChange={(e) =>
                  setPreferences({ autoplay: e.currentTarget.checked })
                }
                color="violet"
              />
            </Group>
          </>
        )}

        <Divider />

        <Group justify="space-between">
          <div>
            <Text fw={500}>{t("auto-scroll")}</Text>
            <Text size="sm" c="dimmed">
              {t("auto-scroll-description")}
            </Text>
          </div>
          <Switch
            checked={userPreferences.autoscroll}
            onChange={(e) =>
              setPreferences({ autoscroll: e.currentTarget.checked })
            }
            color="violet"
          />
        </Group>

        <Divider />

        <Group justify="space-between">
          <div>
            <Text fw={500}>{t("multiagentic-modality")}</Text>
            <Text size="sm" c="dimmed">
              {userPreferences.multiagentic_modality === "isolated"
                ? t("isolated-modality-description")
                : t("grupal-modality-description")}
            </Text>
          </div>
          <Group gap="xs">
            <IconUsers
              size={18}
              opacity={
                userPreferences.multiagentic_modality !== "isolated" ? 1 : 0.3
              }
            />
            <Switch
              checked={userPreferences.multiagentic_modality === "isolated"}
              onChange={(e) => {
                setPreferences({
                  multiagentic_modality: e.currentTarget.checked
                    ? "isolated"
                    : "grupal",
                });
              }}
              color="violet"
            />
            <IconTree
              size={18}
              opacity={
                userPreferences.multiagentic_modality === "isolated" ? 1 : 0.3
              }
            />
          </Group>
        </Group>
      </Stack>
    </Modal>
  );
};

// ─── PluginSelector Modal ────────────────────────────────────────────────────

export const PluginSelectorModal = ({
  opened,
  onClose,
}: {
  opened: boolean;
  onClose: () => void;
}) => {
  const { t } = useTranslation();
  const { togglePlugin, chatState } = useStore((s) => ({
    togglePlugin: s.togglePlugin,
    chatState: s.chatState,
  }));

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={<Title order={4}>{t("plugin-selector")}</Title>}
      centered
      overlayProps={{ backgroundOpacity: 0.55, blur: 3 }}
    >
      <Stack gap="md">
        <Group gap="md" justify="center">
          {Object.values(SYSTEM_PLUGINS).map((p) => {
            const isActive = chatState.selectedPlugins.some(
              (sp) => sp.slug === p.slug
            );
            return (
              <Card
                key={p.slug}
                shadow="sm"
                padding="sm"
                radius="md"
                withBorder
                onClick={() => togglePlugin(p)}
                style={{
                  cursor: "pointer",
                  backgroundColor: isActive
                    ? "var(--mantine-color-violet-light)"
                    : undefined,
                  borderColor: isActive
                    ? "var(--mantine-color-violet-6)"
                    : undefined,
                }}
              >
                <Text fw={500}>{t(p.slug)}</Text>
                <Text size="sm" c="dimmed">
                  {t(p.descriptionTranslationKey)}
                </Text>
              </Card>
            );
          })}
        </Group>
        <Text ta="center" c="dimmed" size="sm">
          {t("more-plugins-coming-soon")}
        </Text>
      </Stack>
    </Modal>
  );
};
