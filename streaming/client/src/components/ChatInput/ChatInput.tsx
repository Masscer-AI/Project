import React, { useRef, useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { SVGS } from "../../assets/svgs";
import { v4 as uuidv4 } from "uuid";
import { useStore } from "../../modules/store";
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
    <div className="flex flex-col justify-center items-center p-0 w-full max-w-[900px] bg-transparent z-[2] gap-0 mt-4 overflow-visible">
      <section className="flex gap-2.5 flex-wrap empty:hidden w-full mb-3 px-4">
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
        <div className="w-full bg-[#282826] border border-[#282826] rounded-2xl overflow-visible">
          <textarea
            className={`w-full ${chatState.writtingMode ? "min-h-[400px] max-h-[90vh]" : "min-h-[70px]"} resize-none px-6 py-4 text-white !bg-[#282826] focus:outline-none focus:ring-0 outline-none transition-all text-base font-sans placeholder:text-[#6b7280] border-0 rounded-2xl`}
            value={textPrompt}
            onChange={handleTextPromptChange}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={t("type-your-message")}
            name="chat-input"
          />
          <div className="flex items-center justify-between px-4 pb-4 pt-3 relative z-10">
            <div className="flex gap-2 button-group relative z-20">
              <SvgButton
                extraClass={
                  chatState.writtingMode
                    ? "!w-12 !h-12 !rounded-full !p-2 bg-white svg-black pressable"
                    : "!w-12 !h-12 !rounded-full !p-2 pressable"
                }
                onClick={toggleWritingMode}
                svg={SVGS.writePen}
                title={t("turn-on-off-writing-mode")}
              />
              <RagSearchOptions />
              <WebSearchDropdown />
              <PluginSelector />
              <ConversationConfig />
            </div>
            <div className="flex gap-2 items-center">
              <SpeechHandler onTranscript={handleAudioTranscript} />
              <button
                onClick={asyncSendMessage}
                className="w-12 h-12 rounded-full aspect-square bg-white flex items-center justify-center transition-all hover:scale-105 active:scale-95 border-0 cursor-pointer shadow-md"
                title={t("send-message")}
              >
                <svg
                  width="20px"
                  height="20px"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M12.0004 18.5816V12.5M12.7976 18.754L15.8103 19.7625C17.4511 20.3118 18.2714 20.5864 18.7773 20.3893C19.2166 20.2182 19.5499 19.8505 19.6771 19.3965C19.8236 18.8737 19.4699 18.0843 18.7624 16.5053L14.2198 6.36709C13.5279 4.82299 13.182 4.05094 12.7001 3.81172C12.2814 3.60388 11.7898 3.60309 11.3705 3.80958C10.8878 4.04726 10.5394 4.8182 9.84259 6.36006L5.25633 16.5082C4.54325 18.086 4.18671 18.875 4.33169 19.3983C4.4576 19.8528 4.78992 20.2216 5.22888 20.394C5.73435 20.5926 6.55603 20.3198 8.19939 19.7744L11.2797 18.752C11.5614 18.6585 11.7023 18.6117 11.8464 18.5933C11.9742 18.5769 12.1036 18.5771 12.2314 18.5938C12.3754 18.6126 12.5162 18.6597 12.7976 18.754Z"
                    stroke="#000000"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </div>
          </div>
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
      bottom="calc(100% + 8px)"
      left="50%"
      transform="translateX(-50%)"
      extraClass=""
      opener={
        <SvgButton
          extraClass={`!w-12 !h-12 !rounded-full !p-2 pressable ${
            chatState.useRag ? "bg-active svg-white" : ""
          }`}
          onClick={toggleUseRag}
          svg={SVGS.document}
          title={t("turn-on-off-rag")}
        />
      }
    >
      <div className="w-full min-w-[250px] max-w-[300px] flex flex-col gap-3 p-4">
        <p className="text-sm">{explanations[String(chatState.useRag)]}</p>
        <SliderInput
          checked={chatState.useRag}
          onChange={(checked) => toggleUseRag()}
          labelTrue={t("use-completions-active")}
          name="use-completions"
          labelFalse={t("use-completions-inactive")}
        />

        <span className="text-xs text-gray-400">
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
        extraClass="!w-12 !h-12 !rounded-full !p-2 pressable"
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
            extraClass={`!w-12 !h-12 !rounded-full !p-2 pressable ${
              hasActiveWebSearch ? "bg-active svg-white" : ""
            }`}
            onClick={toggleWebSearch}
            svg={SVGS.webSearch}
            title={t("turn-on-off-web-search")}
          />
        }
      >
        <div className="w-fit min-w-[180px] flex flex-col gap-2 p-3">
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
            <p className="text-xs text-gray-400">
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
        extraClass={`!w-12 !h-12 !rounded-full !p-2 pressable ${
          chatState.selectedPlugins.length > 0 ? "bg-active svg-white" : ""
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
