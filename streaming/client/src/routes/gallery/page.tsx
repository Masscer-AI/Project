import React, { useCallback, useEffect, useMemo, useState } from "react";
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
  NativeSelect,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
  TextInput,
  Title,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import { useDebouncedValue, useDisclosure } from "@mantine/hooks";
import {
  IconDownload,
  IconFileText,
  IconMessage,
  IconSearch,
  IconMusic,
  IconPhoto,
  IconPlayerPlay,
  IconSettings,
  IconTrash,
  IconVideo,
} from "@tabler/icons-react";
import { AppHeader } from "../../components/AppHeader/AppHeader";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import {
  AttachmentVisibilityModal,
} from "../../components/AttachmentVisibility/AttachmentVisibilityModal";
import { SaveToKnowledgeBaseButton } from "../../components/AttachmentVisibility/SaveToKnowledgeBase";
import {
  DocumentFileIcon,
  getDocumentFileMeta,
} from "../../modules/documentFileMeta";
import { useStore } from "../../modules/store";
import {
  deleteGalleryItem,
  getGalleryItems,
  getTags,
  TGalleryItem,
  TGalleryType,
} from "../../modules/apiCalls";
import { TTag } from "../../types";

const MAX_ITEM_TAGS = 3;

const PAGE_SIZE = 48;

function ItemTagBadges({
  tagIds,
  tagById,
}: {
  tagIds?: number[];
  tagById: Map<number, TTag>;
}) {
  const ids = (tagIds || []).slice(0, MAX_ITEM_TAGS);
  if (ids.length === 0) return null;
  return (
    <Group gap={4} wrap="wrap">
      {ids.map((tid) => (
        <Badge key={tid} size="xs" variant="light" color="gray">
          {tagById.get(tid)?.title || `#${tid}`}
        </Badge>
      ))}
    </Group>
  );
}

function formatDate(iso: string | null, locale: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(d);
}

function GalleryCardActions({
  item,
  tagById,
  onOpenChat,
  onRequestDelete,
  onRequestVisibility,
  onIndexed,
}: {
  item: TGalleryItem;
  tagById: Map<number, TTag>;
  onOpenChat: () => void;
  onRequestDelete: () => void;
  onRequestVisibility: () => void;
  onIndexed?: (item: TGalleryItem) => void;
}) {
  const { t } = useTranslation();
  return (
    <Stack gap={6}>
      <ItemTagBadges tagIds={item.tag_ids} tagById={tagById} />
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
      <Group gap={4} wrap="nowrap">
        {item.can_manage !== false && (
          <Tooltip label={t("settings")}>
            <ActionIcon
              variant="subtle"
              color="gray"
              size="sm"
              onClick={onRequestVisibility}
              aria-label={t("settings")}
            >
              <IconSettings size={16} />
            </ActionIcon>
          </Tooltip>
        )}
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
        <SaveToKnowledgeBaseButton
          attachmentId={item.id}
          type={item.type}
          contentType={item.content_type}
          metadata={item.metadata}
          variant="icon"
          onIndexed={(documentId) =>
            onIndexed?.({
              ...item,
              metadata: {
                ...(item.metadata || {}),
                knowledge_base_document_id: documentId,
              },
            })
          }
        />
        <Tooltip label={t("gallery-delete")}>
          <ActionIcon
            variant="subtle"
            color="red"
            size="sm"
            onClick={onRequestDelete}
            aria-label={t("gallery-delete")}
          >
            <IconTrash size={16} />
          </ActionIcon>
        </Tooltip>
      </Group>
    </Group>
    </Stack>
  );
}

function ImageGalleryCard({
  item,
  dateLabel,
  tagById,
  onOpenChat,
  onRequestDelete,
  onRequestVisibility,
  onIndexed,
}: {
  item: TGalleryItem;
  dateLabel: string;
  tagById: Map<number, TTag>;
  onOpenChat: () => void;
  onRequestDelete: () => void;
  onRequestVisibility: () => void;
  onIndexed?: (item: TGalleryItem) => void;
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
          <GalleryCardActions
            item={item}
            tagById={tagById}
            onOpenChat={onOpenChat}
            onRequestDelete={onRequestDelete}
            onRequestVisibility={onRequestVisibility}
            onIndexed={onIndexed}
          />
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
  tagById,
  onOpenChat,
  onRequestDelete,
  onRequestVisibility,
  onIndexed,
}: {
  item: TGalleryItem;
  dateLabel: string;
  tagById: Map<number, TTag>;
  onOpenChat: () => void;
  onRequestDelete: () => void;
  onRequestVisibility: () => void;
  onIndexed?: (item: TGalleryItem) => void;
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
          <GalleryCardActions
            item={item}
            tagById={tagById}
            onOpenChat={onOpenChat}
            onRequestDelete={onRequestDelete}
            onRequestVisibility={onRequestVisibility}
            onIndexed={onIndexed}
          />
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
  tagById,
  onOpenChat,
  onRequestDelete,
  onRequestVisibility,
  onIndexed,
}: {
  item: TGalleryItem;
  dateLabel: string;
  tagById: Map<number, TTag>;
  onOpenChat: () => void;
  onRequestDelete: () => void;
  onRequestVisibility: () => void;
  onIndexed?: (item: TGalleryItem) => void;
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

        <GalleryCardActions
          item={item}
          tagById={tagById}
          onOpenChat={onOpenChat}
          onRequestDelete={onRequestDelete}
          onRequestVisibility={onRequestVisibility}
          onIndexed={onIndexed}
        />
      </Stack>
    </Card>
  );
}

function DocumentGalleryCard({
  item,
  dateLabel,
  tagById,
  onOpenChat,
  onRequestDelete,
  onRequestVisibility,
  onIndexed,
}: {
  item: TGalleryItem;
  dateLabel: string;
  tagById: Map<number, TTag>;
  onOpenChat: () => void;
  onRequestDelete: () => void;
  onRequestVisibility: () => void;
  onIndexed?: (item: TGalleryItem) => void;
}) {
  const { t } = useTranslation();
  const meta = getDocumentFileMeta(item.name, item.content_type);

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
            <DocumentFileIcon
              name={item.name}
              contentType={item.content_type}
              size={28}
              color="white"
            />
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

        <GalleryCardActions
          item={item}
          tagById={tagById}
          onOpenChat={onOpenChat}
          onRequestDelete={onRequestDelete}
          onRequestVisibility={onRequestVisibility}
          onIndexed={onIndexed}
        />
      </Stack>
    </Card>
  );
}

function GalleryItemCard({
  item,
  locale,
  tagById,
  onDeleted,
  onUpdated,
}: {
  item: TGalleryItem;
  locale: string;
  tagById: Map<number, TTag>;
  onDeleted: (id: string) => void;
  onUpdated: (item: TGalleryItem) => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const dateLabel = formatDate(item.created_at, locale);
  const [confirmOpened, { open: openConfirm, close: closeConfirm }] =
    useDisclosure(false);
  const [visibilityOpened, visibilityHandlers] = useDisclosure(false);
  const [deleting, setDeleting] = useState(false);

  const openChat = () =>
    navigate(`/chat?conversation=${item.conversation_id}`);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deleteGalleryItem(item.id);
      toast.success(t("gallery-deleted"));
      closeConfirm();
      onDeleted(item.id);
    } catch {
      toast.error(t("gallery-delete-error"));
    } finally {
      setDeleting(false);
    }
  };

  const cardProps = {
    item,
    dateLabel,
    tagById,
    onOpenChat: openChat,
    onRequestDelete: openConfirm,
    onRequestVisibility: visibilityHandlers.open,
    onIndexed: onUpdated,
  };

  return (
    <>
      {item.type === "image" && <ImageGalleryCard {...cardProps} />}
      {item.type === "video" && <VideoGalleryCard {...cardProps} />}
      {item.type === "audio" && <AudioGalleryCard {...cardProps} />}
      {item.type === "document" && <DocumentGalleryCard {...cardProps} />}

      <Modal
        opened={confirmOpened}
        onClose={closeConfirm}
        title={t("gallery-delete-confirm-title")}
        centered
      >
        <Stack gap="md">
          <Text size="sm">{t("gallery-delete-confirm")}</Text>
          <Group justify="flex-end" gap="sm">
            <Button
              variant="default"
              onClick={closeConfirm}
              disabled={deleting}
            >
              {t("cancel")}
            </Button>
            <Button color="red" loading={deleting} onClick={() => void handleDelete()}>
              {t("gallery-delete")}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <AttachmentVisibilityModal
        opened={visibilityOpened}
        onClose={visibilityHandlers.close}
        attachmentId={item.id}
        initialItem={item}
        onUpdated={onUpdated}
      />
    </>
  );
}

export default function GalleryPage() {
  const { t, i18n } = useTranslation();
  const chatState = useStore((s) => s.chatState);

  const [tab, setTab] = useState<TGalleryType>("image");
  const [items, setItems] = useState<TGalleryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [orgTags, setOrgTags] = useState<TTag[]>([]);
  const [filterTagId, setFilterTagId] = useState<string>("");
  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebouncedValue(search, 300);

  const tagById = useMemo(
    () => new Map(orgTags.map((tag) => [tag.id, tag])),
    [orgTags]
  );

  useEffect(() => {
    getTags()
      .then((tags) => setOrgTags(tags.filter((tag) => tag.enabled)))
      .catch(() => setOrgTags([]));
  }, []);

  const load = useCallback(
    async (type: TGalleryType, nextOffset: number, append: boolean) => {
      if (append) setLoadingMore(true);
      else setLoading(true);
      try {
        const data = await getGalleryItems({
          type,
          limit: PAGE_SIZE,
          offset: nextOffset,
          tag_id: filterTagId ? parseInt(filterTagId, 10) : null,
          query: debouncedSearch,
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
    [t, filterTagId, debouncedSearch]
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
          flexDirection: "column",
        }}
        className="relative"
      >
        <AppHeader />

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

            <TextInput
              size="sm"
              maw={360}
              placeholder={t("gallery-search")}
              aria-label={t("gallery-search")}
              leftSection={<IconSearch size={16} />}
              value={search}
              onChange={(e) => setSearch(e.currentTarget.value)}
            />

            {orgTags.length > 0 && (
              <NativeSelect
                size="sm"
                maw={280}
                label={t("gallery-filter-tag")}
                value={filterTagId}
                onChange={(e) => {
                  setFilterTagId(e.currentTarget.value);
                  setItems([]);
                  setOffset(0);
                }}
                data={[
                  { value: "", label: t("gallery-filter-tag-all") },
                  ...orgTags.map((tag) => ({
                    value: tag.id.toString(),
                    label: tag.title,
                  })),
                ]}
              />
            )}

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
                      tagById={tagById}
                      onDeleted={(id) => {
                        setItems((prev) => prev.filter((x) => x.id !== id));
                        setTotal((prev) => Math.max(0, prev - 1));
                      }}
                      onUpdated={(updated) => {
                        setItems((prev) =>
                          prev.map((x) => (x.id === updated.id ? updated : x))
                        );
                      }}
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
