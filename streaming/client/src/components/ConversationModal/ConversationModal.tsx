import React, { useEffect, useState } from "react";
import { SvgButton } from "../SvgButton/SvgButton";
import { Modal } from "../Modal/Modal";
import { TConversation } from "../../types";
import { getUserTags, updateConversation } from "../../modules/apiCalls";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { debounce } from "../../modules/utils";
import { Pill } from "../Pill/Pill";
import { useStore } from "../../modules/store";
import { Socket } from "socket.io-client";

export const ConversationModal = ({
  conversation,
}: {
  conversation: TConversation;
}) => {
  const [showModal, setShowModal] = useState(false);
  const [title, setTitle] = useState(conversation.title);
  const [tags, setTags] = useState(conversation.tags || []);

  const { t } = useTranslation();

  const { userTags, socket } = useStore((s) => ({
    userTags: s.userTags,
    socket: s.socket,
  }));

  const onTitleEdit = async (e: React.FocusEvent<HTMLDivElement>) => {
    if (!conversation?.id) return;
    if (e.target.innerText === title) return;

    await updateConversation(conversation?.id, {
      title: e.target.innerText,
    });
    setTitle(e.target.innerText);

    toast.success(t("title-updated"));
  };

  const updateTags = async () => {
    if (!conversation?.id) return;
    await updateConversation(conversation?.id, {
      tags: tags,
    });
  };

  const debouncedTitleEdit = debounce(onTitleEdit, 1000);

  const onTagEdit = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newTags = e.target.value
      .split(",")
      .map((tag) => tag.trim())
      .filter((tag) => tag !== "" && !tags.includes(tag));

    setTags((prev) => [...prev, ...newTags]);
  };
  const debouncedOnTagEdit = debounce(onTagEdit, 1000);

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
    if (conversation.tags !== tags) {
      updateTags();
    }
  }, [tags]);

  useEffect(() => {
    setTitle(conversation.title);
    setTags(conversation.tags || []);
  }, [conversation]);

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
            <h6>{t("title")}</h6>
            <h3
              suppressContentEditableWarning
              contentEditable
              onBlur={debouncedTitleEdit}
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
              className="input"
              defaultValue={""}
              onChange={debouncedOnTagEdit}
              type="text"
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
        </div>
      </Modal>
    </>
  );
};
