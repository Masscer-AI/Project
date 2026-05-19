import React, { useEffect, useMemo } from "react";
import { useLoaderData } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Text } from "@mantine/core";

import { Message } from "../../components/Message/Message";
import { SharedChatHeader } from "../../components/SharedChatHeader/SharedChatHeader";
import { useStore } from "../../modules/store";
import { TChatLoader, TMessage } from "../../types/chatTypes";
import { TVersion } from "../../types";

export default function SharedChatView() {
  const loaderData = useLoaderData() as TChatLoader | null;
  const { setUser, startup, hydrateConversation } = useStore((state) => ({
    setUser: state.setUser,
    startup: state.startup,
    hydrateConversation: state.hydrateConversation,
  }));
  const { t } = useTranslation();

  const conversation = loaderData?.conversation;
  const conversationId = conversation?.id;

  const messages = useMemo(
    () => (conversation?.messages as TMessage[] | undefined) ?? [],
    [conversation?.messages]
  );

  useEffect(() => {
    if (!loaderData || !conversationId) return;
    if (loaderData.user) {
      setUser(loaderData.user);
    }
    hydrateConversation(loaderData.conversation);
    void startup().catch(() => {
      /* anonymous or expired session — shared view still renders */
    });
  }, [conversationId, hydrateConversation, loaderData, setUser, startup]);

  if (!conversation) {
    return (
      <main
        className="flex relative min-h-screen w-full overflow-x-hidden items-center justify-center p-6"
        style={{ backgroundColor: "var(--bg-color)" }}
      >
        <Text c="dimmed" ta="center" maw={480}>
          {t("shared-conversation-unavailable")}
        </Text>
      </main>
    );
  }

  return (
    <main
      className="flex relative min-h-screen w-full overflow-x-hidden"
      style={{ backgroundColor: "var(--bg-color)" }}
    >
      <div className="flex min-h-0 flex-col min-h-screen w-full md:mx-auto md:max-w-[900px] relative z-10 px-4 md:px-4 py-6">
        <SharedChatHeader title={conversation.title || ""} />

        <div className="min-h-0 flex-1 overflow-y-auto flex flex-col w-full pb-6 mt-6 px-1 md:px-2">
          {messages.map((msg, index) => (
            <Message
              {...msg}
              key={msg.id ?? `tmp-${index}`}
              index={index}
              readOnly
              onImageGenerated={() => {}}
              onMessageEdit={(
                _index: number,
                _text: string,
                _versions?: TVersion[]
              ) => {}}
              onMessageDeleted={() => {}}
              numberMessages={messages.length}
            />
          ))}
        </div>
      </div>
    </main>
  );
}
