import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
  Title,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconDownload,
  IconFileSpreadsheet,
  IconFileText,
  IconFileTypePdf,
  IconMenu2,
  IconMessage,
  IconMusic,
  IconPhoto,
  IconPlayerPlay,
  IconPresentation,
  IconVideo,
} from "@tabler/icons-react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import {
  getGalleryItems,
  TGalleryItem,
  TGalleryType,
} from "../../modules/apiCalls";

const PAGE_SIZE = 48;

function formatDate(iso: string | null, locale: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(d);
}

function fileExtension(name: string, contentType: string): string {
  const fromName = name.split(".").pop()?.toLowerCase() || "";
  if (fromName && fromName.length <= 5 && fromName !== name.toLowerCase()) {
    return fromName;
  }
  if (contentType.includes("pdf")) return "pdf";
  if (contentType.includes("spreadsheet") || contentType.includes("excel")) {
    return "xlsx";
  }
  if (contentType.includes("presentation") || contentType.includes("powerpoint")) {
    return "pptx";
  }
  if (contentType.includes("wordprocessing") || contentType.includes("msword")) {
    return "docx";
  }
  return "file";
}

function documentMeta(ext: string): {
  icon: React.ReactNode;
  color: string;
  label: string;
} {
  switch (ext) {
    case "pdf":
      return {
        icon: <IconFileTypePdf size={28} />,
        color: "red",
        label: "PDF",
      };
    case "xlsx":
    case "xls":
    case "csv":
      return {
        icon: <IconFileSpreadsheet size={28} />,
        color: "teal",
        label: ext.toUpperCase(),
      };
    case "pptx":
    case "ppt":
      return {
        icon: <IconPresentation size={28} />,
        color: "orange",
        label: ext.toUpperCase(),
      };
    case "docx":
    case "doc":
      return {
        icon: <IconFileText size={28} />,
        color: "blue",
        label: ext.toUpperCase(),
      };
    default:
      return {
        icon: <IconFileText size={28} />,
        color: "gray",
        label: ext.toUpperCase() || "FILE",
      };
  }
}

function GalleryCardActions({
  item,
  onOpenChat,
}: {
  item: TGalleryItem;
  onOpenChat: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Group gap="xs" justify="space-between" wrap="nowrap">
      <Tooltip label={item.conversation_title || t("gallery-open-conversation")}>
        <Button
          size="xs"
          variant="subtle"
          color="gray"
          leftSection={<IconMessage size={14} />}
          onClick={onOpenChat}
        >
          {t("gallery-open-conversation")}
        </Button>
      </Tooltip>
      <Tooltip label={t("download")}>
        <ActionIcon
          component="a"
          href={item.url}
          download={item.name}
          target="_blank"
          rel="noopener noreferrer"
          variant="subtle"
          color="gray"
          size="sm"
          aria-label={t("download")}
        >
          <IconDownload size={16} />
        </ActionIcon>
      </Tooltip>
    </Group>
  );
}

function ImageGalleryCard({
  item,
  dateLabel,
  onOpenChat,
}: {
  item: TGalleryItem;
  dateLabel: string;
  onOpenChat: () => void;
}) {
  const { t } = useTranslation();
  const [opened, { open, close }] = useDisclosure(false);

  return (
    <>
      <Card padding={0} withBorder radius="md" style={{ overflow: "hidden" }}>
        <UnstyledButton
          onClick={open}
          style={{ display: "block", width: "100%" }}
          aria-label={item.prompt || item.name}
        >
          <Box
            style={{
              aspectRatio: "1 / 1",
              background: "var(--mantine-color-dark-7)",
              overflow: "hidden",
            }}
          >
            <img
              src={item.url}
              alt={item.prompt || item.name}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                display: "block",
              }}
            />
          </Box>
        </UnstyledButton>
        <Stack gap={6} p="sm">
          {item.prompt && (
            <Text size="xs" lineClamp={2} title={item.prompt}>
              {item.prompt}
            </Text>
          )}
          <Text size="xs" c="dimmed">
            {dateLabel}
          </Text>
          <GalleryCardActions item={item} onOpenChat={onOpenChat} />
        </Stack>
      </Card>

      <Modal
        opened={opened}
        onClose={close}
        title={
          <Group justify="space-between" wrap="nowrap" w="100%">
            <Text fw={600} size="lg">
              {t("image-preview")}
            </Text>
            <Tooltip label={t("download")}>
              <ActionIcon
                component="a"
                href={item.url}
                download={item.name}
                target="_blank"
                rel="noopener noreferrer"
                variant="subtle"
                color="gray"
              >
                <IconDownload size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
        }
        size="lg"
        centered
      >
        <Stack gap="md">
          {item.prompt && (
            <Text size="sm" c="dimmed">
              {item.prompt}
            </Text>
          )}
          <img
            src={item.url}
            alt={item.prompt || item.name}
            style={{
              width: "100%",
              maxHeight: "calc(100vh - 200px)",
              objectFit: "contain",
              borderRadius: 8,
            }}
          />
        </Stack>
      </Modal>
    </>
  );
}

function VideoGalleryCard({
  item,
  dateLabel,
  onOpenChat,
}: {
  item: TGalleryItem;
  dateLabel: string;
  onOpenChat: () => void;
}) {
  const { t } = useTranslation();
  const [opened, { open, close }] = useDisclosure(false);

  return (
    <>
      <Card padding={0} withBorder radius="md" style={{ overflow: "hidden" }}>
        <UnstyledButton
          onClick={open}
          style={{ display: "block", width: "100%", position: "relative" }}
          aria-label={item.prompt || item.name}
        >
          <Box
            style={{
              aspectRatio: "16 / 9",
              background: "var(--mantine-color-dark-7)",
              overflow: "hidden",
            }}
          >
            <video
              src={item.url}
              muted
              playsInline
              preload="metadata"
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                display: "block",
              }}
            />
            <Box
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "rgba(0,0,0,0.35)",
              }}
            >
              <Box
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: "50%",
                  background: "rgba(0,0,0,0.65)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <IconPlayerPlay size={22} color="white" />
              </Box>
            </Box>
          </Box>
        </UnstyledButton>
        <Stack gap={6} p="sm">
          {item.prompt && (
            <Text size="xs" lineClamp={2} title={item.prompt}>
              {item.prompt}
            </Text>
          )}
          <Text size="xs" c="dimmed">
            {dateLabel}
          </Text>
          <GalleryCardActions item={item} onOpenChat={onOpenChat} />
        </Stack>
      </Card>

      <Modal
        opened={opened}
        onClose={close}
        title={
          <Group justify="space-between" wrap="nowrap" w="100%">
            <Text fw={600} size="lg">
              {t("generated-video")}
            </Text>
            <Tooltip label={t("download")}>
              <ActionIcon
                component="a"
                href={item.url}
                download={item.name}
                target="_blank"
                rel="noopener noreferrer"
                variant="subtle"
                color="gray"
              >
                <IconDownload size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
        }
        size="lg"
        centered
      >
        <Stack gap="md">
          {item.prompt && (
            <Text size="sm" c="dimmed">
              {item.prompt}
            </Text>
          )}
          <video
            src={item.url}
            controls
            autoPlay
            playsInline
            style={{
              width: "100%",
              maxHeight: "calc(100vh - 200px)",
              borderRadius: 8,
            }}
          />
        </Stack>
      </Modal>
    </>
  );
}

function AudioGalleryCard({
  item,
  dateLabel,
  onOpenChat,
}: {
  item: TGalleryItem;
  dateLabel: string;
  onOpenChat: () => void;
}) {
  return (
    <Card padding="md" withBorder radius="md">
      <Stack gap="sm">
        <Group gap="sm" wrap="nowrap">
          <Box
            style={{
              width: 44,
              height: 44,
              borderRadius: 10,
              background: "var(--mantine-color-violet-9)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <IconMusic size={22} />
          </Box>
          <Box style={{ minWidth: 0, flex: 1 }}>
            <Text size="sm" fw={500} lineClamp={1} title={item.name}>
              {item.name}
            </Text>
            <Text size="xs" c="dimmed">
              {dateLabel}
            </Text>
          </Box>
        </Group>

        <audio
          controls
          src={item.url}
          preload="metadata"
          playsInline
          style={{ width: "100%" }}
        />

        {item.prompt && (
          <Text size="xs" c="dimmed" lineClamp={2} title={item.prompt}>
            {item.prompt}
          </Text>
        )}

        <GalleryCardActions item={item} onOpenChat={onOpenChat} />
      </Stack>
    </Card>
  );
}

function DocumentGalleryCard({
  item,
  dateLabel,
  onOpenChat,
}: {
  item: TGalleryItem;
  dateLabel: string;
  onOpenChat: () => void;
}) {
  const { t } = useTranslation();
  const ext = fileExtension(item.name, item.content_type);
  const meta = documentMeta(ext);

  return (
    <Card padding="md" withBorder radius="md">
      <Stack gap="sm">
        <Group gap="sm" wrap="nowrap" align="flex-start">
          <Box
            style={{
              width: 52,
              height: 52,
              borderRadius: 12,
              background: `var(--mantine-color-${meta.color}-9)`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {meta.icon}
          </Box>
          <Box style={{ minWidth: 0, flex: 1 }}>
            <Group gap={6} mb={4}>
              <Badge size="xs" variant="light" color={meta.color}>
                {meta.label}
              </Badge>
            </Group>
            <Text size="sm" fw={500} lineClamp={2} title={item.name}>
              {item.name}
            </Text>
            <Text size="xs" c="dimmed" mt={4}>
              {dateLabel}
            </Text>
          </Box>
        </Group>

        <Button
          component="a"
          href={item.url}
          download={item.name}
          target="_blank"
          rel="noopener noreferrer"
          variant="light"
          leftSection={<IconDownload size={16} />}
          fullWidth
        >
          {t("download")}
        </Button>

        <GalleryCardActions item={item} onOpenChat={onOpenChat} />
      </Stack>
    </Card>
  );
}

function GalleryItemCard({
  item,
  locale,
}: {
  item: TGalleryItem;
  locale: string;
}) {
  const navigate = useNavigate();
  const dateLabel = formatDate(item.created_at, locale);
  const openChat = () =>
    navigate(`/chat?conversation=${item.conversation_id}`);

  if (item.type === "image") {
    return (
      <ImageGalleryCard
        item={item}
        dateLabel={dateLabel}
        onOpenChat={openChat}
      />
    );
  }
  if (item.type === "video") {
    return (
      <VideoGalleryCard
        item={item}
        dateLabel={dateLabel}
        onOpenChat={openChat}
      />
    );
  }
  if (item.type === "audio") {
    return (
      <AudioGalleryCard
        item={item}
        dateLabel={dateLabel}
        onOpenChat={openChat}
      />
    );
  }
  return (
    <DocumentGalleryCard
      item={item}
      dateLabel={dateLabel}
      onOpenChat={openChat}
    />
  );
}

export default function GalleryPage() {
  const { t, i18n } = useTranslation();
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));

  const [tab, setTab] = useState<TGalleryType>("image");
  const [items, setItems] = useState<TGalleryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  const load = useCallback(
    async (type: TGalleryType, nextOffset: number, append: boolean) => {
      if (append) setLoadingMore(true);
      else setLoading(true);
      try {
        const data = await getGalleryItems({
          type,
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        setItems((prev) =>
          append ? [...prev, ...data.results] : data.results
        );
        setTotal(data.total);
        setOffset(data.offset);
        setHasNext(data.has_next);
      } catch {
        toast.error(t("gallery-load-error"));
        if (!append) {
          setItems([]);
          setTotal(0);
          setHasNext(false);
        }
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [t]
  );

  useEffect(() => {
    void load(tab, 0, false);
  }, [tab, load]);

  const onTabChange = (value: string | null) => {
    if (!value) return;
    setTab(value as TGalleryType);
    setItems([]);
    setOffset(0);
  };

  const gridCols =
    tab === "image"
      ? { base: 1, xs: 2, sm: 3, md: 4 }
      : tab === "video"
        ? { base: 1, sm: 2, md: 3 }
        : { base: 1, sm: 2, md: 3 };

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
              aria-label={t("open-sidebar")}
            >
              <IconMenu2 size={20} />
            </ActionIcon>
          </Box>
        )}

        <Box maw={1100} w="100%" mx="auto">
          <Stack gap="lg">
            <div>
              <Title order={2}>{t("gallery-title")}</Title>
              <Text c="dimmed" size="sm" mt={4}>
                {t("gallery-subtitle")}
              </Text>
            </div>

            <Tabs value={tab} onChange={onTabChange}>
              <Tabs.List>
                <Tabs.Tab value="image" leftSection={<IconPhoto size={16} />}>
                  {t("images")}
                </Tabs.Tab>
                <Tabs.Tab value="video" leftSection={<IconVideo size={16} />}>
                  {t("video")}
                </Tabs.Tab>
                <Tabs.Tab value="audio" leftSection={<IconMusic size={16} />}>
                  {t("audio")}
                </Tabs.Tab>
                <Tabs.Tab
                  value="document"
                  leftSection={<IconFileText size={16} />}
                >
                  {t("documents")}
                </Tabs.Tab>
              </Tabs.List>
            </Tabs>

            {loading ? (
              <Group justify="center" py="xl">
                <Loader />
              </Group>
            ) : items.length === 0 ? (
              <Stack align="center" gap="xs" py="xl">
                <Text c="dimmed">{t("gallery-empty")}</Text>
                <Text c="dimmed" size="sm">
                  {t("gallery-empty-hint")}
                </Text>
              </Stack>
            ) : (
              <Stack gap="md">
                <Text size="sm" c="dimmed">
                  {t("gallery-count", { count: total })}
                </Text>
                <SimpleGrid cols={gridCols} spacing="md">
                  {items.map((item) => (
                    <GalleryItemCard
                      key={item.id}
                      item={item}
                      locale={i18n.language}
                    />
                  ))}
                </SimpleGrid>
                {hasNext && (
                  <Group justify="center">
                    <Button
                      variant="default"
                      loading={loadingMore}
                      onClick={() => void load(tab, offset + PAGE_SIZE, true)}
                    >
                      {t("gallery-load-more")}
                    </Button>
                  </Group>
                )}
              </Stack>
            )}
          </Stack>
        </Box>
      </div>
    </main>
  );
}
