import React, { useRef, useEffect, useCallback, useState } from "react";
import { SVGS } from "../../assets/svgs";
import { v4 as uuidv4 } from "uuid";
import { useStore } from "../../modules/store";
import "./ChatInput.css";
import toast from "react-hot-toast";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import { SvgButton } from "../SvgButton/SvgButton";
import { TConversationData } from "../../types/chatTypes";
import { useTranslation } from "react-i18next";
import { debounce } from "../../modules/utils";
import { getSuggestion } from "../../modules/apiCalls";

interface ChatInputProps {
  handleSendMessage: () => void;
  handleKeyDown: (event) => void;
  conversation: TConversationData;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  handleSendMessage,
  handleKeyDown,
  conversation,
}) => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const {
    input,
    setInput,
    attachments,
    addAttachment,
    chatState,
    toggleWebSearch,
    toggleUseRag,
    toggleWritingMode,
  } = useStore((state) => ({
    input: state.input,
    setInput: state.setInput,
    attachments: state.chatState.attachments,
    addAttachment: state.addAttachment,
    chatState: state.chatState,
    toggleWebSearch: state.toggleWebSearch,
    toggleWritingMode: state.toggleWrittingMode,
    toggleUseRag: state.toggleUseRag,
  }));

  // const [suggestion, setSuggestion] = useState("");
  const allowedImageTypes = [
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
  ];
  const allowedDocumentTypes = [
    "application/pdf",
    "text/plain",
    "text/html",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ];

  // const debouncedGetSuggestion = useCallback(
  //   debounce(async (inputContent: string) => {
  //     if (inputContent.length > 0) {
  //       const result = await getSuggestion(inputContent);
  //       if (typeof result.suggestion === "string") {
  //         setSuggestion(result.suggestion);
  //       }
  //     }
  //   }, 1000),
  //   []
  // );

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

          addAttachment(
            {
              content: result as string,
              type: "image",
              name: id,
              file: blob,
            },
            conversation.id
          );
        };
        if (blob) reader.readAsDataURL(blob);
      }
    }
  };

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

          addAttachment(
            {
              content: result as string,
              file: file,
              type: file.type,
              name: file.name,
            },
            conversation.id
          );
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

  // useEffect(() => {
  //   debouncedGetSuggestion(input);
  // }, [input]);
  return (
    <div className="chat-input">
      <section className="attachments">
        {attachments.map(({ content, type, name, file }, index) => (
          <Thumbnail
            // file={file}
            name={name}
            type={type}
            src={content}
            key={index}
            index={index}
          />
        ))}
      </section>
      <section>
        <textarea
          className={chatState.writtingMode ? "big-size" : ""}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={t("type-your-message")}
          name="chat-input"
        />
        {/* {suggestion && <p className="suggestion">{suggestion}</p>} */}
      </section>
      <section className="mt-small">
        <div className="flex-x">
          {/* <button className="button" onClick={handleSendMessage}>{SVGS.send}</button> */}
          <SvgButton
            title={t("send-message")}
            onClick={handleSendMessage}
            svg={SVGS.send}
          />
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
              title={t("add-files")}
              svg={SVGS.addDocument}
            />
          </label>
          <SvgButton
            extraClass={chatState.writtingMode ? "active" : ""}
            onClick={toggleWritingMode}
            svg={SVGS.writePen}
            title={t("turn-on-off-writing-mode")}
          />
          <SvgButton
            extraClass={chatState.webSearch ? "active" : ""}
            onClick={toggleWebSearch}
            svg={SVGS.webSearch}
            title={t("turn-on-off-web-search")}
          />
          <SvgButton
            extraClass={chatState.useRag ? "active" : ""}
            onClick={toggleUseRag}
            svg={SVGS.document}
            title={t("turn-on-off-rag")}
          />
        </div>
      </section>
    </div>
  );
};
