import React, { useRef, useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { v4 as uuidv4 } from "uuid";
import { useStore } from "../../modules/store";
import toast from "react-hot-toast";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import { useTranslation } from "react-i18next";
import { generateDocumentBrief, getDocuments, syncDriveDocument, updateAgent } from "../../modules/apiCalls";
import { SpeechHandler } from "../SpeechHandler/SpeechHandler";
import { WebsiteFetcher } from "../WebsiteFetcher/WebsiteFetcher";
import { DriveFilePicker } from "../DriveFilePicker/DriveFilePicker";
import { TAttachment, TDocument } from "../../types";

import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { PoweredByMasscer } from "../PoweredByMasscer/PoweredByMasscer";
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
  IconSettings,
  IconPlus,
  IconFilePlus,
  IconLink,
  IconTrash,
  IconBrandGoogleDrive,
  IconRefresh,
  IconTree,
  IconUsers,
  IconAdjustments,
  IconSquareRounded,
} from "@tabler/icons-react";
import {
  cancelAgentTask,
  isLockedMasscerAgent,
  isComplianceAssistant,
} from "../../modules/apiCalls";
import { agentsInChatSelectionOrder } from "../../modules/agentSelection";
import { ToolsSelectorModal } from "../ToolsSelectorModal/ToolsSelectorModal";

interface ChatInputProps {
  handleSendMessage: (input: string) => Promise<boolean>;
  initialInput: string;
  readOnly?: boolean;
  readOnlyMessage?: string;
  composerMode?: "agent" | "human" | "readonly";
}

const allowedDocumentTypes = [
  "application/pdf",
  "text/plain",
  "text/html",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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

export const ChatInput: React.FC<ChatInputProps> = ({
  handleSendMessage,
  initialInput,
  readOnly = false,
  readOnlyMessage,
  composerMode,
}) => {
  const { t } = useTranslation();
  const {
    attachments,
    addAttachment,
    chatState,
    toggleWritingMode,
    setSpecifiedUrls,
    agentTaskStatus,
    agentTaskConversationId,
    conversationId,
    agents,
  } = useStore((state) => ({
    attachments: state.chatState.attachments,
    addAttachment: state.addAttachment,
    chatState: state.chatState,
    toggleWritingMode: state.toggleWrittingMode,
    setSpecifiedUrls: state.setSpecifiedUrls,
    agentTaskStatus: state.agentTaskStatus,
    agentTaskConversationId: state.agentTaskConversationId,
    conversationId: state.conversation?.id,
    agents: state.agents,
  }));

  const showStopButton =
    !!agentTaskStatus &&
    !!agentTaskConversationId &&
    agentTaskConversationId === conversationId;

  useEffect(() => {
    console.debug("[agent-task] stop button visibility", {
      showStopButton,
      agentTaskStatus,
      agentTaskConversationId,
      conversationId,
      scopedOut:
        !!agentTaskStatus &&
        !!agentTaskConversationId &&
        agentTaskConversationId !== conversationId,
    });
  }, [
    showStopButton,
    agentTaskStatus,
    agentTaskConversationId,
    conversationId,
  ]);

  const isLockedMasscerChat =
    chatState.selectedAgents.length === 1 &&
    (() => {
      const slug = chatState.selectedAgents[0];
      const agent = agents.find((a) => a.slug === slug);
      return agent != null && isLockedMasscerAgent(agent);
    })();
  const isComplianceChat =
    chatState.selectedAgents.length === 1 &&
    (() => {
      const slug = chatState.selectedAgents[0];
      const agent = agents.find((a) => a.slug === slug);
      return agent != null && isComplianceAssistant(agent);
    })();

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
          const dataUrl = target.result;
          if (!dataUrl) return;
          const id = uuidv4();

          if (!blob) return;

          addAttachment({
            content: dataUrl as string,
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
      if (showStopButton) return;
      const messageSent = await handleSendMessage(textPrompt);
      if (messageSent) setTextPrompt("");
    }
  };

  const setAgentTaskStatus = useStore((state) => state.setAgentTaskStatus);

  const handleCancelAgentTask = async () => {
    if (!conversationId) return;
    console.debug("[agent-task] stop clicked — optimistic clear", {
      conversationId,
    });
    try {
      setAgentTaskStatus(null);
      await cancelAgentTask(conversationId);
      console.debug("[agent-task] cancel API ok", { conversationId });
      toast.success(t("task-cancelled") || "Task cancelled");
    } catch (error) {
      console.debug("[agent-task] cancel API failed (stop already cleared)", {
        conversationId,
        error,
      });
      toast.error(t("error-cancelling-task") || "Error cancelling task");
    }
  };

  const asyncSendMessage = async () => {
    const messageSent = await handleSendMessage(textPrompt);
    if (messageSent) setTextPrompt("");
  };

  useHotkeys("ctrl+alt+w", () => toggleWritingMode(), {
    enableOnFormTags: true,
  });

  const mode =
    composerMode ?? (readOnly ? "readonly" : "agent");

  if (mode === "readonly") {
    return (
      <div className="flex flex-col justify-center items-center p-0 w-full max-w-[900px] bg-transparent z-[2] gap-0 mt-4 overflow-visible">
        <div className="w-full rounded-lg px-4 py-3 text-center" style={{ background: "var(--bg-contrast-color)", border: "1px solid var(--hovered-color)" }}>
          <Text size="sm" c="dimmed">{readOnlyMessage ?? t("view-only-mode")}</Text>
        </div>
      </div>
    );
  }

  if (mode === "human") {
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
        <section className="w-full flex flex-col items-center justify-center relative overflow-visible">
          <div
            className="flex min-h-0 w-full flex-col rounded-none md:rounded-2xl overflow-hidden relative"
            style={{ background: "var(--bg-contrast-color)", border: "1px solid var(--hovered-color)" }}
          >
            <MantineTextarea
              autosize
              minRows={1}
              maxRows={6}
              classNames={{
                input:
                  "!bg-transparent !border-0 !text-base md:!text-sm !font-sans focus:!ring-0 focus:!outline-none !px-3 md:!px-5 !py-2 md:!py-3 !max-h-[calc(100dvh-12rem)] !min-h-0 !resize-none !overflow-x-hidden !overflow-y-auto",
              }}
              styles={{ input: { color: "var(--font-color)" } }}
              placeholder={t("human-takeover-composer-placeholder")}
              value={textPrompt}
              onChange={(e) => setTextPrompt(e.currentTarget.value)}
              onPaste={handlePaste}
              onKeyDown={async (event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  const messageSent = await handleSendMessage(textPrompt);
                  if (messageSent) setTextPrompt("");
                }
              }}
            />
            <div className="flex shrink-0 items-center justify-between px-1 md:px-4 pb-1 md:pb-3 pt-1 md:pt-2">
              <div className="flex gap-2">
                <PlusMenu existingFilesOnly={true} />
              </div>
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                radius="xl"
                onClick={() => void asyncSendMessage()}
                aria-label={t("send-message")}
              >
                <IconSend size={18} />
              </ActionIcon>
            </div>
          </div>
          <PoweredByMasscer
            className="text-center text-xs mt-1"
            style={{ color: "var(--font-color)", opacity: 0.4 }}
          />
        </section>
      </div>
    );
  }

  return (
    <div className="flex flex-col justify-center items-center p-0 w-full max-w-[900px] bg-transparent z-[2] gap-0 mt-4 overflow-visible">
      <section className="chat-input-attachments flex gap-2.5 flex-nowrap overflow-x-auto empty:hidden w-full mb-3 px-4 [scrollbar-width:thin] [scrollbar-color:rgba(128,128,128,0.3)_transparent] [&::-webkit-scrollbar]:h-1 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-[rgba(128,128,128,0.3)] [&::-webkit-scrollbar-thumb]:rounded-full">
        {(chatState.specifiedUrls || []).map((u) => (
          <div
            key={u.url}
            title={u.url}
            className="width-150 document-attachment bg-contrast rounded padding-small"
            style={{
              display: "flex",
              gap: 8,
              alignItems: "center",
              textDecoration: "none",
              color: "inherit",
            }}
          >
            <a
              href={u.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "flex",
                gap: 8,
                alignItems: "center",
                textDecoration: "none",
                color: "inherit",
                flex: 1,
                minWidth: 0,
              }}
            >
              <IconLink size={20} />
              <p className="cut-text-to-line" style={{ flex: 1, minWidth: 0 }}>
                {u.url}
              </p>
            </a>
            <ActionIcon
              variant="subtle"
              color="red"
              size="sm"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                const next = (chatState.specifiedUrls || []).filter(
                  (x) => x.url !== u.url
                );
                setSpecifiedUrls(next);
              }}
              aria-label={t("delete") || "Delete"}
              title={t("delete") || "Delete"}
            >
              <IconTrash size={16} />
            </ActionIcon>
          </div>
        ))}
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
      <section className="w-full flex flex-col items-center justify-center relative overflow-visible">
        <div
          className="flex min-h-0 w-full flex-col rounded-none md:rounded-2xl overflow-hidden relative"
          style={{ background: "var(--bg-contrast-color)", border: "1px solid var(--hovered-color)" }}
        >
          <MantineTextarea
            autosize
            minRows={chatState.writtingMode ? 8 : 1}
            classNames={{
              input:
                "!bg-transparent !border-0 !text-base md:!text-sm !font-sans focus:!ring-0 focus:!outline-none !px-3 md:!px-5 !py-2 md:!py-3 !max-h-[calc(100dvh-12rem)] md:!max-h-[calc(100dvh-14rem)] !min-h-0 !resize-none !overflow-x-hidden !overflow-y-auto",
              wrapper: "!bg-transparent !min-h-0",
              root: "!bg-transparent !min-h-0",
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
          <div className="flex shrink-0 items-center justify-between px-1 md:px-4 pb-1 md:pb-4 pt-1 md:pt-3 relative z-10 min-w-0">
            <div className="flex gap-2 relative z-20 min-w-0 flex-shrink">
              <PlusMenu
                existingFilesOnly={false}
                alwaysAllowUpload={isLockedMasscerChat}
                skipKnowledgeBase={isComplianceChat}
              />
              {!isLockedMasscerChat && <ToolsMenu />}
            </div>
            <div className="flex gap-2 items-center flex-shrink-0">
              {isTranscribeEnabled && (
                <SpeechHandler onTranscript={handleAudioTranscript} />
              )}
              {showStopButton ? (
                <ActionIcon
                  onClick={handleCancelAgentTask}
                  variant="subtle"
                  color="red"
                  size="lg"
                  radius="xl"
                  aria-label={t("stop-generating") || "Stop generating"}
                  title={t("stop-generating") || "Stop generating"}
                >
                  <IconSquareRounded size={18} fill="currentColor" />
                </ActionIcon>
              ) : (
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
              )}
            </div>
          </div>
        </div>
        <PoweredByMasscer
          className="text-center text-xs mt-1"
          style={{ color: "var(--font-color)", opacity: 0.4 }}
        />
      </section>
    </div>
  );
};

const PlusMenu = ({
  existingFilesOnly = false,
  alwaysAllowUpload = false,
  skipKnowledgeBase = false,
}: {
  existingFilesOnly?: boolean;
  alwaysAllowUpload?: boolean;
  skipKnowledgeBase?: boolean;
}) => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const addAttachment = useStore((s) => s.addAttachment);
  const attachments = useStore((s) => s.chatState.attachments);
  const addFilesFlag = useIsFeatureEnabled("add-files-to-chat");
  const isAddFilesEnabled = alwaysAllowUpload || addFilesFlag;
  const trainAgentsFlag = useIsFeatureEnabled("train-agents");
  const webScrapingFlag = useIsFeatureEnabled("web-scraping");
  const isTrainAgentsEnabled = !skipKnowledgeBase && trainAgentsFlag;
  const isWebScrapingEnabled = !skipKnowledgeBase && webScrapingFlag;
  const isDriveImportEnabled =
    useIsFeatureEnabled("can-manage-integrations") === true &&
    isTrainAgentsEnabled === true;

  const [ragConfigOpened, { open: openRagConfig, close: closeRagConfig }] =
    useDisclosure(false);
  const [websiteFetcherOpen, setWebsiteFetcherOpen] = useState(false);
  const [drivePickerOpen, setDrivePickerOpen] = useState(false);

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
          const dataUrl = target.result;
          if (!dataUrl) return;
          addAttachment({
            content: dataUrl as string,
            file: file,
            type: file.type,
            name: file.name,
            text: "",
          }, existingFilesOnly);
        };
        reader.readAsDataURL(file);
      } else {
        toast.error(t("file-type-not-allowed"));
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const hasAnyPlusOption =
    isAddFilesEnabled ||
    isTrainAgentsEnabled ||
    isWebScrapingEnabled ||
    isDriveImportEnabled;

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        onChange={addDocument}
        style={{ display: "none" }}
        accept=".png,.jpeg,.jpg,.gif,.webp,.pdf,.txt,.html,.doc,.docx,.xlsx"
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
          {isDriveImportEnabled && (
            <Menu.Item
              leftSection={<IconBrandGoogleDrive size={18} />}
              onClick={() => setDrivePickerOpen(true)}
            >
              {t("drive-import-menu")}
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

      <RagConfig
        opened={ragConfigOpened}
        onClose={closeRagConfig}
        existingFilesOnly={existingFilesOnly}
      />
      <WebsiteFetcher
        isOpen={websiteFetcherOpen}
        onClose={() => setWebsiteFetcherOpen(false)}
      />
      <DriveFilePicker
        opened={drivePickerOpen}
        onClose={() => setDrivePickerOpen(false)}
      />
    </>
  );
};

const ToolsMenu = () => {
  const { t } = useTranslation();
  const { chatState, toggleWritingMode } = useStore((state) => ({
    chatState: state.chatState,
    toggleWritingMode: state.toggleWrittingMode,
  }));

  const [settingsOpened, { open: openSettings, close: closeSettings }] =
    useDisclosure(false);
  const [toolsOpened, { open: openTools, close: closeTools }] =
    useDisclosure(false);

  const hasActiveTools =
    Object.values(chatState.toolsByAgent).some((names) => names.length > 0) ||
    (chatState.specifiedUrls?.length ?? 0) > 0 ||
    chatState.writtingMode;

  return (
    <>
      <Menu shadow="md" width={220} position="top-start" withArrow>
        <Menu.Target>
          <Indicator
            disabled={!hasActiveTools}
            processing
            color="violet"
            size={8}
          >
            <ActionIcon variant="subtle" color="gray" size="lg">
              <IconSettings size={20} />
            </ActionIcon>
          </Indicator>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Item
            leftSection={<IconAdjustments size={18} />}
            onClick={openTools}
          >
            {t("select-tools") || "Select tools"}
          </Menu.Item>
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
          <Menu.Item
            leftSection={<IconSettings size={18} />}
            onClick={openSettings}
          >
            {t("conversation-settings") || "Settings"}
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>

      <SelectToolsModal opened={toolsOpened} onClose={closeTools} />

      <ConversationConfigModal
        opened={settingsOpened}
        onClose={closeSettings}
      />
    </>
  );
};

const SelectToolsModal = ({
  opened,
  onClose,
}: {
  opened: boolean;
  onClose: () => void;
}) => {
  const { t } = useTranslation();
  const { chatState, agents, setAgentToolNames } = useStore((state) => ({
    chatState: state.chatState,
    agents: state.agents,
    setAgentToolNames: state.setAgentToolNames,
  }));
  const savingRef = useRef<Record<string, string[]>>({});

  const selectedAgents = agentsInChatSelectionOrder(
    agents,
    chatState.selectedAgents
  );

  const handleChange = async (slug: string, names: string[]) => {
    const previous =
      chatState.toolsByAgent[slug] ??
      agents.find((a) => a.slug === slug)?.pre_approved_tools ??
      [];
    setAgentToolNames(slug, names);
    savingRef.current[slug] = previous;
    try {
      const saved = await updateAgent(slug, { pre_approved_tools: names });
      const savedTools = Array.isArray(saved?.pre_approved_tools)
        ? saved.pre_approved_tools
        : names;
      setAgentToolNames(slug, savedTools);
    } catch (e) {
      console.error(e);
      setAgentToolNames(slug, savingRef.current[slug] ?? previous);
      toast.error(t("agent-tools-save-error") || "Could not save agent tools");
    }
  };

  return (
    <ToolsSelectorModal
      opened={opened}
      onClose={onClose}
      title={t("select-tools") || "Select tools"}
      description={t("chat-tools-desc")}
      agents={selectedAgents.map((a) => ({ slug: a.slug, name: a.name }))}
      valueByAgent={chatState.toolsByAgent}
      onChange={handleChange}
      emptyMessage={t("select-at-least-one-agent-to-chat")}
    />
  );
};

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
          const dataUrl = target.result;
          if (!dataUrl) return;
          addAttachment({
            content: dataUrl as string,
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
        accept=".png,.jpeg,.jpg,.gif,.webp,.pdf,.txt,.html,.doc,.docx,.xlsx"
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

const RagConfig = ({
  opened,
  onClose,
  existingFilesOnly = false,
}: {
  opened: boolean;
  onClose: () => void;
  existingFilesOnly?: boolean;
}) => {
  const [documents, setDocuments] = useState([] as TDocument[]);
  const [isLoading, setIsLoading] = useState(false);

  const { t } = useTranslation();

  useEffect(() => {
    if (opened) getDocs();
  }, [opened]);

  const getDocs = async () => {
    setIsLoading(true);
    const docs = await getDocuments({ hasFileOnly: existingFilesOnly });
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
          documents.map((d) => (
            <DocumentCard d={d} key={d.id} existingFilesOnly={existingFilesOnly} />
          ))}
        {!isLoading && documents.length === 0 && (
          <Text c="dimmed" py="xl">
            {t("no-documents-found")}
          </Text>
        )}
      </Group>
    </Modal>
  );
};

const DocumentCard = ({
  d,
  existingFilesOnly = false,
}: {
  d: TDocument;
  existingFilesOnly?: boolean;
}) => {
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
        type: d.content_type || "text/plain",
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

  const syncFromDrive = async () => {
    try {
      toast.loading(t("drive-sync-loading"), { id: `sync-${d.id}` });
      const updated = await syncDriveDocument(d.id);
      if (isAttached) {
        const attachment: TAttachment = {
          content: updated.text,
          name: updated.name,
          type: updated.content_type || "text/plain",
          id: updated.id,
          mode: "all_possible_text",
          text: updated.text,
        };
        const idx = chatState.attachments.findIndex((a) => a.id == d.id);
        if (idx !== -1) {
          removeAttatchment(idx);
          addAttatchment(attachment, true);
        }
      }
      toast.success(t("drive-sync-success"), { id: `sync-${d.id}` });
    } catch {
      toast.error(t("drive-sync-error"), { id: `sync-${d.id}` });
    }
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
      {existingFilesOnly && (
        <Text size="xs" c="dimmed" mb="xs">
          {d.has_file ? "File available" : "No source file"}
          {d.is_drive_linked ? ` · ${t("drive-linked-badge")}` : ""}
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
        {d.is_drive_linked && (
          <Button
            onClick={syncFromDrive}
            leftSection={<IconRefresh size={16} />}
            variant="light"
            size="xs"
          >
            {t("drive-sync-action")}
          </Button>
        )}
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

const ConversationConfigModal = ({
  opened,
  onClose,
}: {
  opened: boolean;
  onClose: () => void;
}) => {
  const { userPreferences, setPreferences, chatState, updateChatState } =
    useStore((s) => ({
      userPreferences: s.userPreferences,
      setPreferences: s.setPreferences,
      chatState: s.chatState,
      updateChatState: s.updateChatState,
    }));
  const { t } = useTranslation();
  const isMultiAgentEnabled = useIsFeatureEnabled("multi-agent-chat");
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

        {isMultiAgentEnabled && (
          <>
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
          </>
        )}
      </Stack>
    </Modal>
  );
};
