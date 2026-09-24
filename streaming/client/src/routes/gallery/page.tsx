import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { AppPage } from "../../components/AppPage/AppPage";
import {
  AttachmentVisibilityModal,
} from "../../components/AttachmentVisibility/AttachmentVisibilityModal";
import { SaveToKnowledgeBaseButton } from "../../components/AttachmentVisibility/SaveToKnowledgeBase";
import {
  DocumentFileIcon,
  getDocumentFileMeta,
} from "../../modules/documentFileMeta";
import {
  deleteGalleryItem,
  getGalleryItems,
  getTags,
  TGalleryItem,
  TGalleryType,
} from "../../modules/apiCalls";
import { TTag } from "../../types";
import "./gallery.css";

const MAX_ITEM_TAGS = 3;

const PAGE_SIZE = 48;

const EMPTY_COUNTS: Record<TGalleryType, number> = {
  image: 0,
  video: 0,
  audio: 0,
  document: 0,
};

function TabCount({ count, active }: { count: number; active: boolean }) {
  return (
    <Badge size="xs" variant={active ? "filled" : "light"} radius="xl">
      {count}
    </Badge>
  );
}

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

function GalleryPrompt({
  prompt,
  size = "xs",
}: {
  prompt: string;
  size?: "xs" | "sm";
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [overflows, setOverflows] = useState(false);
  const textRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = textRef.current;
    if (!el || expanded) return;
    setOverflows(el.scrollHeight > el.clientHeight + 2);
  }, [prompt, expanded]);

  return (
    <Stack gap={4}>
      <Text ref={textRef} size={size} lineClamp={expanded ? undefined : 2}>
        {prompt}
      </Text>
      {(overflows || expanded) && (
        <UnstyledButton
          onClick={(e) => {
            e.stopPropagation();
            setExpanded((open) => !open);
          }}
        >
          <Text size="xs" c="dimmed" td="underline">
            {expanded ? t("gallery-read-less") : t("gallery-read-more")}
          </Text>
        </UnstyledButton>
      )}
    </Stack>
  );
}

function GalleryCardActions({
  item,
  onOpenChat,
  onRequestDelete,
  onRequestVisibility,
  onIndexed,
}: {
  item: TGalleryItem;
  onOpenChat: () => void;
  onRequestDelete: () => void;
  onRequestVisibility: () => void;
  onIndexed?: (item: TGalleryItem) => void;
}) {
  const { t } = useTranslation();
  return (
    <Group
      className="gallery-card-actions"
      gap="xs"
      justify="space-between"
      wrap="nowrap"
    >
      <Button
        size="xs"
        variant="light"
        color="gray"
        leftSection={<IconMessage size={14} />}
        onClick={onOpenChat}
      >
        {t("gallery-open-conversation")}
      </Button>
      <Group gap={4} wrap="nowrap">
        {item.can_manage !== false && (
          <Tooltip label={t("settings")}>
            <ActionIcon
              variant="light"
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
            variant="light"
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
            variant="light"
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
      <Card className="gallery-card" padding={0} withBorder radius="md" style={{ overflow: "hidden" }}>
        <Box className="gallery-card-media">
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
          <GalleryCardActions
            item={item}
            onOpenChat={onOpenChat}
            onRequestDelete={onRequestDelete}
            onRequestVisibility={onRequestVisibility}
            onIndexed={onIndexed}
          />
        </Box>
        <Stack gap={6} p="sm">
          {item.prompt && <GalleryPrompt prompt={item.prompt} />}
          <Text size="xs" c="dimmed">
            {dateLabel}
          </Text>
          <ItemTagBadges tagIds={item.tag_ids} tagById={tagById} />
        </Stack>
      </Card>

      <Modal
        opened={opened}
        onClose={close}
        title={t("image-preview")}
        size="lg"
        centered
      >
        <Stack gap="md">
          {item.prompt && <GalleryPrompt prompt={item.prompt} size="sm" />}
          <img
            src={item.url}
            alt={item.prompt || item.name}
            style={{
              width: "100%",
              maxHeight: "calc(100vh - 240px)",
              objectFit: "contain",
              borderRadius: 8,
            }}
          />
          <GalleryCardActions
            item={item}
            onOpenChat={onOpenChat}
            onRequestDelete={onRequestDelete}
            onRequestVisibility={onRequestVisibility}
            onIndexed={onIndexed}
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
      <Card className="gallery-card" padding={0} withBorder radius="md" style={{ overflow: "hidden" }}>
        <Box className="gallery-card-media">
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
          <GalleryCardActions
            item={item}
            onOpenChat={onOpenChat}
            onRequestDelete={onRequestDelete}
            onRequestVisibility={onRequestVisibility}
            onIndexed={onIndexed}
          />
        </Box>
        <Stack gap={6} p="sm">
          {item.prompt && <GalleryPrompt prompt={item.prompt} />}
          <Text size="xs" c="dimmed">
            {dateLabel}
          </Text>
          <ItemTagBadges tagIds={item.tag_ids} tagById={tagById} />
        </Stack>
      </Card>

      <Modal
        opened={opened}
        onClose={close}
        title={t("generated-video")}
        size="lg"
        centered
      >
        <Stack gap="md">
          {item.prompt && <GalleryPrompt prompt={item.prompt} size="sm" />}
          <video
            src={item.url}
            controls
            autoPlay
            playsInline
            style={{
              width: "100%",
              maxHeight: "calc(100vh - 240px)",
              borderRadius: 8,
            }}
          />
          <GalleryCardActions
            item={item}
            onOpenChat={onOpenChat}
            onRequestDelete={onRequestDelete}
            onRequestVisibility={onRequestVisibility}
            onIndexed={onIndexed}
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
    <Card className="gallery-card" padding="md" withBorder radius="md">
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

        {item.prompt && <GalleryPrompt prompt={item.prompt} />}
        <ItemTagBadges tagIds={item.tag_ids} tagById={tagById} />

        <GalleryCardActions
          item={item}
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
  const meta = getDocumentFileMeta(item.name, item.content_type);

  return (
    <Card className="gallery-card" padding="md" withBorder radius="md">
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
        <ItemTagBadges tagIds={item.tag_ids} tagById={tagById} />

        <GalleryCardActions
          item={item}
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

  const [tab, setTab] = useState<TGalleryType>("image");
  const [items, setItems] = useState<TGalleryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState<Record<TGalleryType, number>>(EMPTY_COUNTS);
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
        setCounts({ ...EMPTY_COUNTS, ...(data.counts || {}) });
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
    <AppPage title={t("gallery-title")}>
        <Box maw={1100} w="100%" mx="auto">
          <Stack gap="lg">
            <Text c="dimmed" size="sm">
              {t("gallery-subtitle")}
            </Text>

            <Group justify="space-between" align="flex-end" gap="md" wrap="wrap">
            <Tabs value={tab} onChange={onTabChange}>
              <Tabs.List>
                <Tabs.Tab
                  value="image"
                  leftSection={<IconPhoto size={16} />}
                  rightSection={<TabCount count={counts.image} active={tab === "image"} />}
                >
                  {t("images")}
                </Tabs.Tab>
                <Tabs.Tab
                  value="video"
                  leftSection={<IconVideo size={16} />}
                  rightSection={<TabCount count={counts.video} active={tab === "video"} />}
                >
                  {t("video")}
                </Tabs.Tab>
                <Tabs.Tab
                  value="audio"
                  leftSection={<IconMusic size={16} />}
                  rightSection={<TabCount count={counts.audio} active={tab === "audio"} />}
                >
                  {t("audio")}
                </Tabs.Tab>
                <Tabs.Tab
                  value="document"
                  leftSection={<IconFileText size={16} />}
                  rightSection={<TabCount count={counts.document} active={tab === "document"} />}
                >
                  {t("documents")}
                </Tabs.Tab>
              </Tabs.List>
            </Tabs>
            <Group gap="sm" wrap="wrap" align="flex-end">
            <TextInput
              size="sm"
              maw={280}
              placeholder={t("gallery-search")}
              aria-label={t("gallery-search")}
              leftSection={<IconSearch size={16} />}
              value={search}
              onChange={(e) => setSearch(e.currentTarget.value)}
            />

            {orgTags.length > 0 && (
              <NativeSelect
                size="sm"
                maw={220}
                aria-label={t("gallery-filter-tag")}
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
            </Group>
            </Group>

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
                        setCounts((prev) => ({
                          ...prev,
                          [item.type]: Math.max(0, (prev[item.type] || 0) - 1),
                        }));
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
    </AppPage>
  );
}
