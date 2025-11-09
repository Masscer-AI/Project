import React, { useRef, useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { SVGS } from "../../assets/svgs";
import { v4 as uuidv4 } from "uuid";
import { useStore } from "../../modules/store";
import "./ChatInput.css";
import toast from "react-hot-toast";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import { SvgButton } from "../SvgButton/SvgButton";

import { useTranslation } from "react-i18next";
import { generateDocumentBrief, getDocuments } from "../../modules/apiCalls";
import { SpeechHandler } from "../SpeechHandler/SpeechHandler";
import { FloatingDropdown } from "../Dropdown/Dropdown";
import { Modal } from "../Modal/Modal";
import { WebsiteFetcher } from "../WebsiteFetcher/WebsiteFetcher";

import { TAttachment, TDocument } from "../../types";
import { SliderInput } from "../SimpleForm/SliderInput";
import { Loader } from "../Loader/Loader";
import { SYSTEM_PLUGINS } from "../../modules/plugins";

interface ChatInputProps {
  handleSendMessage: (input: string) => Promise<boolean>;
  initialInput: string;
}

const getCommand = (text: string): string | null => {
  // Regex para capturar el comando después de "k/"
  const regex = /k\/(.*)$/;
  const match = text.match(regex);
  return match ? match[1] : null; // Si hay coincidencia, devuelve el comando; si no, null.
};

export const ChatInput: React.FC<ChatInputProps> = ({
  handleSendMessage,
  initialInput,
}) => {
  const { t } = useTranslation();
  const {
    attachments,
    addAttachment,
    chatState,
    toggleWebSearch,

    toggleWritingMode,
  } = useStore((state) => ({
    attachments: state.chatState.attachments,
    addAttachment: state.addAttachment,
    chatState: state.chatState,
    toggleWebSearch: state.toggleWebSearch,
    toggleWritingMode: state.toggleWrittingMode,
  }));

  const [textPrompt, setTextPrompt] = useState(initialInput);

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

    // addAttachment({
    //   content: base64Audio,
    //   type: "audio",
    //   name: uuidv4(),
    //   file: null,
    //   text: "",
    // });
  };

  const handleKeyDown = async (event) => {
    if (event.key === "Enter" && event.shiftKey) {
      return;
    }

    if (event.key === "Enter" && chatState.writtingMode) {
      return;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      const result = await handleSendMessage(textPrompt);

      if (result) {
        setTextPrompt("");
      }
    }
  };

  const asyncSendMessage = async () => {
    const result = await handleSendMessage(textPrompt);
    if (result) {
      setTextPrompt("");
    }
  };

  useHotkeys(
    "ctrl+alt+w",
    () => {
      toggleWritingMode();
    },
    {
      enableOnFormTags: true,
    }
  );

  const handleTextPromptChange = (
    e: React.ChangeEvent<HTMLTextAreaElement>
  ) => {
    setTextPrompt(e.target.value);
  };

  return (
    <div className="chat-input">
      <section className="attachments">
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
      <section>
        <textarea
          className={chatState.writtingMode ? "big-size" : ""}
          value={textPrompt}
          onChange={handleTextPromptChange}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={t("type-your-message")}
          name="chat-input"
        />
      </section>
      <section>
        <div className="flex-x gap-small button-group">
          <SvgButton
            title={t("send-message")}
            extraClass="active-on-hover pressable rounded"
            onClick={asyncSendMessage}
            svg={SVGS.send}
          />

          <SvgButton
            extraClass={
              chatState.writtingMode
                ? "bg-active svg-white pressable rounded active-on-hover"
                : "pressable rounded active-on-hover"
            }
            onClick={toggleWritingMode}
            svg={SVGS.writePen}
            title={t("turn-on-off-writing-mode")}
          />
          <RagSearchOptions />
          <WebSearchDropdown />
          <PluginSelector />
          <SpeechHandler onTranscript={handleAudioTranscript} />
          <ConversationConfig />
          {/* <WebsiteFetcher /> */}
        </div>
      </section>
    </div>
  );
};

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

  const openDocuments = () => {
    if (!fileInputRef || !fileInputRef.current) return;
    fileInputRef.current.click();
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
        <SvgButton
          onClick={openDocuments}
          svg={SVGS.addDocument}
          size="big"
          text={t("add-files")}
          extraClass="border-active"
        />
      </label>
    </>
  );
};

const RagSearchOptions = () => {
  const { toggleUseRag, chatState } = useStore((state) => ({
    toggleUseRag: state.toggleUseRag,
    chatState: state.chatState,
  }));

  const [isConfigOpen, setIsConfigOpen] = useState(false);

  const { t } = useTranslation();

  const explanations = {
    true: t("use-completions-active-explanation"),
    false: t("use-completions-inactive-explanation"),
  };

  return (
    <FloatingDropdown
      bottom="100%"
      left="50%"
      transform="translateX(-50%)"
      opener={
        <SvgButton
          extraClass={`pressable rounded active-on-hover ${
            chatState.useRag ? "bg-active svg-white" : ""
          }`}
          onClick={toggleUseRag}
          svg={SVGS.document}
          title={t("turn-on-off-rag")}
        />
      }
    >
      <div className="width-300 flex-y gap-medium">
        <p>{explanations[String(chatState.useRag)]}</p>
        <SliderInput
          checked={chatState.useRag}
          onChange={(checked) => toggleUseRag()}
          labelTrue={t("use-completions-active")}
          name="use-completions"
          labelFalse={t("use-completions-inactive")}
        />

        <span className="text-mini text-secondary">
          {t(
            "the-completions-configuration-do-not-affect-the-documents-used-only-specifies-if-completions-are-used"
          )}
        </span>
        <SvgButton
          onClick={() => setIsConfigOpen(true)}
          text={t("add-existing-documents")}
          extraClass="border-active"
          svg={SVGS.plus}
          size="big"
        />
        <FileLoader />

        {isConfigOpen && <RagConfig hide={() => setIsConfigOpen(false)} />}
      </div>
    </FloatingDropdown>
  );
};

const RagConfig = ({ hide }: { hide: () => void }) => {
  const [documents, setDocuments] = useState([] as TDocument[]);
  const [isLoading, setIsLoading] = useState(false);

  const { addAttatchment, chatState, removeAttatchment } = useStore((s) => ({
    addAttatchment: s.addAttachment,
    chatState: s.chatState,
    removeAttatchment: s.deleteAttachment,
  }));

  const { t } = useTranslation();

  useEffect(() => {
    getDocs();
  }, []);

  const getDocs = async () => {
    setIsLoading(true);
    const docs = await getDocuments();
    setDocuments(docs);
    setIsLoading(false);
  };

  return (
    <Modal
      header={
        <h3 className="text-center padding-big">
          {t("select-documents-to-use")}
        </h3>
      }
      hide={hide}
    >
      <div className="d-flex gap-small wrap-wrap">
        {isLoading && (
          <div className="flex-x justify-center w-100 h-100 align-center">
            <Loader text={t("loading-documents")} />
          </div>
        )}

        {documents.map((d) => (
          <DocumentCard d={d} key={d.id} />
        ))}

        {documents.length === 0 && (
          <div className="flex-x justify-center w-100 h-100 align-center">
            <span>{t("no-documents-found")}</span>
          </div>
        )}
      </div>
    </Modal>
  );
};

const DocumentCard = ({ d }: { d: TDocument }) => {
  const { addAttatchment, chatState, removeAttatchment } = useStore((s) => ({
    addAttatchment: s.addAttachment,
    chatState: s.chatState,
    removeAttatchment: s.deleteAttachment,
  }));

  const { t } = useTranslation();

  const toggleDocument = (d: TDocument) => {
    if (chatState.attachments.findIndex((a) => a.id == d.id) === -1) {
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
      removeAttatchment(chatState.attachments.findIndex((a) => a.id == d.id));
    }
  };

  const generateBrief = async () => {
    toast.success(t("generating-brief"));
    await generateDocumentBrief(String(d.id));
  };

  return (
    <div
      className={`card pressable ${
        chatState.attachments.findIndex((a) => a.id == d.id) != -1
          ? "bg-active"
          : ""
      }`}
    >
      <h4>{d.name}</h4>
      {d.brief && <p title={d.brief}>{d.brief.slice(0, 200)}...</p>}
      <SvgButton
        onClick={() => toggleDocument(d)}
        svg={SVGS.plus}
        size="big"
        text={
          chatState.attachments.findIndex((a) => a.id == d.id) != -1
            ? t("remove-document")
            : t("add-document")
        }
        extraClass={
          chatState.attachments.findIndex((a) => a.id == d.id) != -1
            ? ""
            : "border-active"
        }
      />
      {!d.brief && (
        <SvgButton
          extraClass="border-active"
          text={t("generate-brief")}
          onClick={generateBrief}
          svg={SVGS.plus}
          size="big"
        />
      )}
    </div>
  );
};

const ConversationConfig = () => {
  const { userPreferences, setPreferences } = useStore((s) => ({
    userPreferences: s.userPreferences,
    setPreferences: s.setPreferences,
    chatState: s.chatState,
    updateChatState: s.updateChatState,
  }));
  const [isOpened, setIsOpened] = useState(false);

  const { t } = useTranslation();

  const updateMaxMemoryMessages = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.value) {
      setPreferences({
        max_memory_messages: parseInt(e.target.value),
      });
    }
  };

  return (
    <>
      <SvgButton
        extraClass="pressable active-on-hover rounded"
        onClick={() => setIsOpened(true)}
        svg={SVGS.options}
      />
      <Modal
        header={<h3 className="padding-big">{t("conversation-settings")}</h3>}
        visible={isOpened}
        hide={() => setIsOpened(false)}
      >
        <div className="flex-y gap-medium">
          <div className="flex-y gap-small align-center  ">
            <h5>{t("max-memory-messages")}</h5>
            <span>{t("max-memory-messages-description")}</span>
            <input
              type="number"
              className="input padding-small"
              value={userPreferences.max_memory_messages}
              onChange={updateMaxMemoryMessages}
              min={0}
            />
          </div>
          <hr className="separator" />
          <div className="flex-y gap-small align-center">
            <section className="flex-x gap-medium align-center justify-center w-100">
              <h5>{t("auto-play")}</h5>
              <SliderInput
                name="autoplay"
                checked={userPreferences.autoplay}
                onChange={(checked) => setPreferences({ autoplay: checked })}
              />
            </section>
            <span>{t("auto-play-description")}</span>
          </div>
          <hr className="separator" />
          <div className="flex-y gap-small align-center">
            <section className="flex-x gap-medium align-center justify-center w-100">
              <h5>{t("auto-scroll")}</h5>
              <SliderInput
                name="autoscroll"
                checked={userPreferences.autoscroll}
                onChange={(checked) => setPreferences({ autoscroll: checked })}
              />
            </section>
            <span>{t("auto-scroll-description")}</span>
          </div>
          <hr className="separator" />
          <div className="flex-y gap-small align-center">
            <section className="flex-x gap-medium align-center justify-center w-100">
              <h5>{t("multiagentic-modality")}</h5>
              <SliderInput
                name="multiagentic-modality"
                labelTrue={t("isolated")}
                labelFalse={t("grupal")}
                svgTrue={SVGS.palmeras}
                svgFalse={SVGS.team}
                checked={userPreferences.multiagentic_modality === "isolated"}
                onChange={(checked) => {
                  setPreferences({
                    multiagentic_modality: checked ? "isolated" : "grupal",
                  });
                }}
              />
            </section>
            <span>
              {userPreferences.multiagentic_modality === "isolated"
                ? t("isolated-modality-description")
                : t("grupal-modality-description")}
            </span>
          </div>
        </div>
      </Modal>
    </>
  );
};

const WebSearchDropdown = () => {
  const { t } = useTranslation();
  const { toggleWebSearch, chatState } = useStore((state) => ({
    toggleWebSearch: state.toggleWebSearch,
    chatState: state.chatState,
  }));
  const [isWebsiteFetcherOpen, setIsWebsiteFetcherOpen] = useState(false);

  const hasActiveWebSearch =
    chatState.webSearch || (chatState.specifiedUrls?.length ?? 0) > 0;

  return (
    <>
      <FloatingDropdown
        bottom="100%"
        left="50%"
        transform="translateX(-50%)"
        opener={
          <SvgButton
            extraClass={`pressable active-on-hover rounded ${
              hasActiveWebSearch ? "bg-active svg-white" : ""
            }`}
            onClick={toggleWebSearch}
            svg={SVGS.webSearch}
            title={t("turn-on-off-web-search")}
          />
        }
      >
        <div className="width-200 flex-y gap-small">
          <SvgButton
            extraClass={`pressable rounded ${
              chatState.webSearch ? "bg-active svg-white" : ""
            }`}
            onClick={toggleWebSearch}
            svg={SVGS.webSearch}
            text={t("auto-search") || "Auto Search"}
            title={t("turn-on-off-web-search")}
          />
          <SvgButton
            extraClass={`pressable rounded ${
              (chatState.specifiedUrls?.length ?? 0) > 0
                ? "bg-active svg-white"
                : ""
            }`}
            onClick={() => setIsWebsiteFetcherOpen(true)}
            svg={SVGS.webSearch}
            text={t("fetch-urls") || "Fetch URLs"}
            title={t("specify-urls-to-fetch") || "Specify URLs to fetch"}
          />
          {(chatState.specifiedUrls?.length ?? 0) > 0 && (
            <p className="text-mini text-secondary">
              {t("urls-selected") || "URLs selected"}:{" "}
              {chatState.specifiedUrls.length}
            </p>
          )}
        </div>
      </FloatingDropdown>
      <WebsiteFetcher
        isOpen={isWebsiteFetcherOpen}
        onClose={() => setIsWebsiteFetcherOpen(false)}
      />
    </>
  );
};

export const PluginSelector = () => {
  const { t } = useTranslation();
  const { togglePlugin, chatState } = useStore((s) => ({
    togglePlugin: s.togglePlugin,
    chatState: s.chatState,
  }));
  const [isOpened, setIsOpened] = useState(false);
  return (
    <>
      <SvgButton
        onClick={() => setIsOpened(true)}
        svg={SVGS.plugin}
        size="big"
        extraClass={`pressable active-on-hover rounded ${
          chatState.selectedPlugins.length > 0 ? "bg-active" : ""
        }`}
      />
      <Modal
        header={<h3 className="padding-big">{t("plugin-selector")}</h3>}
        visible={isOpened}
        hide={() => setIsOpened(false)}
      >
        <div className="d-flex gap-medium wrap-wrap justify-center">
          {Object.values(SYSTEM_PLUGINS).map((p) => (
            <div
              key={p.slug}
              className={`card pressable ${
                chatState.selectedPlugins.some((sp) => sp.slug === p.slug)
                  ? "bg-active"
                  : ""
              }`}
              onClick={() => togglePlugin(p)}
            >
              <h5>{t(p.slug)}</h5>
              <p>{t(p.descriptionTranslationKey)}</p>
            </div>
          ))}
          <h4 className="text-secondary">{t("more-plugins-coming-soon")}</h4>
        </div>
      </Modal>
    </>
  );
};
