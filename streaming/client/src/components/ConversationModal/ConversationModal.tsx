import React, { useEffect, useState } from "react";
import { Modal } from "../Modal/Modal";
import { TConversation } from "../../types";
import { updateConversation } from "../../modules/apiCalls";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { debounce } from "../../modules/utils";
import { Pill } from "../Pill/Pill";
import { useStore } from "../../modules/store";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";

export const ConversationModal = ({
  conversation,
}: {
  conversation: TConversation;
}) => {
  const [showModal, setShowModal] = useState(false);
  const [title, setTitle] = useState(conversation.title);
  const [tags, setTags] = useState(conversation.tags || []);
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);

  const { t } = useTranslation();

  const { userTags, socket } = useStore((s) => ({
    userTags: s.userTags,
    socket: s.socket,
  }));

  const onTitleEdit = async (e: React.FocusEvent<HTMLDivElement>) => {
    if (!conversation?.id) return;
    setTitle(e.target.innerText);
  };

  // const updateTags = async () => {
  //   if (!conversation?.id) return;
  //   setTags(tags);
  // };

  const onTagEdit = (e: React.FocusEvent<HTMLInputElement>) => {
    const newTags = e.target.value
      .split(",")
      .map((tag) => tag.trim())
      .filter((tag) => tag !== "" && !tags.includes(tag));

    setTags((prev) => [...prev, ...newTags]);
  };

  useEffect(() => {
    socket.on("title_updated", (data) => {
      if (data.message.conversation_id === conversation.id) {
        setTitle(data.message.title);
      }
    });
    return () => {
      socket.off("title_updated");
    };
  }, [socket, conversation]);

  useEffect(() => {
    setTitle(conversation.title);
    setTags(conversation.tags || []);
  }, [conversation]);

  const handleSave = async () => {
    await updateConversation(conversation.id, {
      title: title,
      tags: tags,
    });
    toast.success(t("conversation-updated"));
    setShowModal(false);
  };

  return (
    <>
      <p onClick={() => setShowModal(true)} className="cutted-text pressable">
        {title ? `${title.slice(0, 25)}...` : t("conversation-without-title")}
      </p>
      <Modal
        visible={showModal}
        header={<h3 className="padding-big">{t("conversation-editor")}</h3>}
        hide={() => setShowModal(false)}
      >
        <div className="flex-y gap-big">
          <div className="flex-y gap-small">
            <h6 className="text-white">{t("title")}</h6>
            <h3
              suppressContentEditableWarning
              contentEditable
              onBlur={onTitleEdit}
              className="w-full p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)] min-h-[48px]"
              style={{ 
                outline: 'none',
                wordBreak: 'break-word'
              }}
            >
              {title}
            </h3>
          </div>
          <h6>{t("tags")}</h6>
          {tags && tags.length > 0 && (
            <div className="flex-x gap-small">
              {tags.map((tag) => (
                <Pill extraClass="bg-hovered " key={tag}>
                  {tag}
                  <span
                    className="cursor-pointer text-secondary padding-small danger-color-on-hover rounded"
                    onClick={() => setTags(tags.filter((t) => t !== tag))}
                  >
                    &times;
                  </span>
                </Pill>
              ))}
            </div>
          )}

          <div className="flex-x gap-small wrap-wrap">
            <input
              className="input w-full"
              defaultValue={""}
              // onChange={debouncedOnTagEdit}
              type="text"
              onBlur={onTagEdit}
              placeholder={t("tag-examples")}
            />
          </div>
          <div className="flex-x gap-small wrap-wrap align-center">
            <h6 className="text-secondary">{t("previously-used-tags")}</h6>
            {userTags
              .filter((tag) => !tags.includes(tag))
              .map((tag) => (
                <Pill
                  onClick={() => setTags([...tags, tag])}
                  key={tag}
                  extraClass="bg-hovered active-on-hover"
                >
                  {tag}
                </Pill>
              ))}
          </div>
          <div className="flex justify-center w-full">
            <button
              className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
                hoveredButton === 'save' 
                  ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
                  : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
              }`}
              style={{ transform: 'none' }}
              onMouseEnter={() => setHoveredButton('save')}
              onMouseLeave={() => setHoveredButton(null)}
              onClick={handleSave}
            >
              <span className="flex items-center justify-center w-5 h-5 [&>svg]:w-5 [&>svg]:h-5">{SVGS.save}</span>
              <span>{t("save")}</span>
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
};
