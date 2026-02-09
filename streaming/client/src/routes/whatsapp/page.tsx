import React, { useEffect, useState } from "react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import "./page.css";
import { useLoaderData } from "react-router-dom";
import {
  getWhatsappConversations,
  getWhatsappConversationMessages,
  sendMessageToConversation,
  updateWhatsappNumber,
} from "../../modules/apiCalls";
import MarkdownRenderer from "../../components/MarkdownRenderer/MarkdownRenderer";
import { AgentSelector } from "../../components/AgentSelector/AgentSelector";
import toast from "react-hot-toast";

import {
  ActionIcon,
  Box,
  Button,
  Card,
  Group,
  Modal,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { IconMenu2, IconSend, IconDeviceFloppy } from "@tabler/icons-react";

export default function Whatsapp() {
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));

  const { numbers } = useLoaderData() as { numbers: any[] };

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
            WhatsApp
          </Title>
          <Text mb="md">
            Masscer AI lets you use AI Agents inside WhatsApp, boosting your
            customer service and collecting information about your contacts.
          </Text>

          <Title order={4} mb="sm">
            Your WhatsApp numbers
          </Title>
          <Stack gap="md">
            {numbers.map((number) => (
              <WhatsAppNumber key={number.id} {...number} />
            ))}
          </Stack>
        </Box>
      </div>
    </main>
  );
}

const WhatsAppNumber = ({
  number,
  agent,
  conversations_count,
  name,
}: {
  number: string;
  agent: any;
  conversations_count: number;
  name: string;
}) => {
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [conversations, setConversations] = useState<any[]>([]);
  const [nameInput, setNameInput] = useState(name ? name : "");

  useEffect(() => {
    getWhatsappConversations().then((res) => {
      setConversations(res as any[]);
    });
  }, []);

  const changeAgent = (slug: string) => {
    updateWhatsappNumber(number, { slug }).then(() => {
      toast.success("Agent changed");
    });
  };

  const updateName = () => {
    updateWhatsappNumber(number, { name: nameInput }).then(() => {
      toast.success("Name updated");
    });
  };

  return (
    <>
      <Card
        withBorder
        padding="lg"
        style={{ cursor: "pointer" }}
        onClick={() => setIsModalVisible(true)}
      >
        <Title order={4} ta="center">
          {name}
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
        opened={isModalVisible}
        onClose={() => setIsModalVisible(false)}
        title="Conversations"
        centered
        size="lg"
      >
        <Stack gap="md">
          <Group gap="sm" align="flex-end">
            <TextInput
              label="Name"
              value={nameInput}
              onChange={(e) => setNameInput(e.currentTarget.value)}
              style={{ flex: 1 }}
            />
            <Button
              leftSection={<IconDeviceFloppy size={16} />}
              onClick={updateName}
            >
              Update
            </Button>
          </Group>

          <div>
            <Text size="sm" fw={500} mb={4}>
              Change the agent for this number
            </Text>
            <AgentSelector
              onSelectAgent={changeAgent}
              selectedSlug={agent.slug}
            />
          </div>

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
  user_number,
  id,
  summary,
  sentiment,
}: {
  title: string;
  user_number: string;
  id: string;
  summary: string;
  sentiment: string;
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
        <Text size="sm">
          {user_number} <span>{sentiment}</span>
        </Text>
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
              onChange={(e) => setMessageInput(e.currentTarget.value)}
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
  content,
  message_type,
  created_at,
  reaction,
}: {
  content: string;
  message_type: string;
  created_at: string;
  reaction: string;
}) => {
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
      className={`text-center d-flex flex-y message ${message_type.toLowerCase()}`}
    >
      <div className="text-left message-text">
        <MarkdownRenderer markdown={content} />
        {reaction && <span className="reaction">{reaction} ✔️✔️</span>}
      </div>
      <Text size="xs" c="dimmed" p="xs">
        {formattedDate}
      </Text>
    </div>
  );
};
