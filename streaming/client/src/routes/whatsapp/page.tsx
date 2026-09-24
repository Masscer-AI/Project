import React, { useEffect, useState } from "react";
import { AppPage } from "../../components/AppPage/AppPage";
import "./page.css";
import { getWhatsappNumbers, getWhatsappTemplates } from "../../modules/apiCalls";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import {
  Badge,
  Box,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  Stack,
  Tabs,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconBrandWhatsapp,
  IconChevronRight,
  IconMessages,
  IconRobot,
  IconSettings,
  IconSparkles,
  IconTemplate,
  IconUsers,
} from "@tabler/icons-react";
import {
  countEnabledCapabilities,
  formatWhatsappPhone,
  type WhatsappLine,
  type WhatsappTemplate,
} from "./shared";
import { WhatsappTemplatePreview } from "./TemplatePreview";

type WhatsappPageTab = "lines" | "templates";

function parseWhatsappPageTab(raw: string | null): WhatsappPageTab {
  if (raw === "templates") return "templates";
  return "lines";
}

function StatChip({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
}) {
  return (
    <Tooltip label={label} withArrow>
      <Group
        gap={6}
        wrap="nowrap"
        px="sm"
        py={6}
        style={{
          borderRadius: "var(--mantine-radius-sm)",
          background: "var(--mantine-color-dark-6)",
          border: "1px solid var(--mantine-color-dark-4)",
        }}
      >
        <ThemeIcon size={22} radius="sm" variant="light" color="gray">
          {icon}
        </ThemeIcon>
        <Stack gap={0}>
          <Text size="xs" c="dimmed" lh={1.2}>
            {label}
          </Text>
          <Text size="sm" fw={600} lh={1.2}>
            {value}
          </Text>
        </Stack>
      </Group>
    </Tooltip>
  );
}

function WhatsappLineCard({ line }: { line: WhatsappLine }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const phone = formatWhatsappPhone(line.number);
  const toolsEnabled = countEnabledCapabilities(line.capabilities);
  const displayName = (line.name || "").trim() || phone;

  return (
    <Card
      withBorder
      padding="md"
      radius="md"
      style={{ cursor: "pointer" }}
      onClick={() => navigate(`/whatsapp/${line.id}`)}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
        <Group gap="md" wrap="nowrap" style={{ minWidth: 0, flex: 1 }}>
          <ThemeIcon
            size={48}
            radius="md"
            variant="light"
            color="teal"
            style={{ flexShrink: 0 }}
          >
            <IconBrandWhatsapp size={28} />
          </ThemeIcon>

          <Stack gap={4} style={{ minWidth: 0, flex: 1 }}>
            <Group gap="xs" wrap="wrap">
              <Text fw={700} size="lg" lineClamp={1}>
                {displayName}
              </Text>
              {line.verified ? (
                <Badge size="sm" variant="light" color="teal">
                  {t("whatsapp-verified")}
                </Badge>
              ) : (
                <Badge size="sm" variant="light" color="gray">
                  {t("whatsapp-unverified")}
                </Badge>
              )}
            </Group>

            <Text size="sm" c="dimmed" ff="monospace">
              {phone}
            </Text>

            <Group gap="xs" mt={6} wrap="wrap">
              <StatChip
                icon={<IconRobot size={14} />}
                label={t("agent")}
                value={line.agent?.name || "—"}
              />
              <StatChip
                icon={<IconMessages size={14} />}
                label={t("whatsapp-conversations")}
                value={line.conversations_count ?? 0}
              />
              <StatChip
                icon={<IconSparkles size={14} />}
                label={t("whatsapp-tools-enabled")}
                value={toolsEnabled}
              />
            </Group>
          </Stack>
        </Group>

        <IconChevronRight
          size={20}
          style={{ flexShrink: 0, opacity: 0.45, marginTop: 4 }}
        />
      </Group>

      <Group
        justify="flex-end"
        gap="xs"
        mt="md"
        onClick={(e) => e.stopPropagation()}
      >
        <Button
          size="xs"
          variant="default"
          leftSection={<IconUsers size={14} />}
          onClick={() => navigate(`/whatsapp/${line.id}?tab=contacts`)}
        >
          {t("whatsapp-contacts")}
        </Button>
        <Button
          size="xs"
          variant="default"
          leftSection={<IconSettings size={14} />}
          onClick={() => navigate(`/whatsapp/${line.id}?tab=settings`)}
        >
          {t("whatsapp-tab-settings")}
        </Button>
        <Button
          size="xs"
          variant="light"
          color="teal"
          leftSection={<IconMessages size={14} />}
          onClick={() =>
            navigate(`/dashboard?wsNumberId=${line.id}&channel=whatsapp`)
          }
        >
          {t("view-conversations")}
        </Button>
      </Group>
    </Card>
  );
}

function templateCategoryColor(category: string): string {
  const key = (category || "").toUpperCase();
  if (key === "MARKETING") return "violet";
  if (key === "AUTHENTICATION") return "gray";
  return "blue";
}

function templateCategoryLabel(category: string, t: (key: string) => string): string {
  const key = (category || "").toUpperCase();
  if (key === "MARKETING") return t("whatsapp-template-category-marketing");
  if (key === "AUTHENTICATION") return t("whatsapp-template-category-authentication");
  return t("whatsapp-template-category-utility");
}

function TemplateMetaBadges({ template }: { template: WhatsappTemplate }) {
  const { t } = useTranslation();
  const category = (template.category || "").toUpperCase();
  return (
    <Group gap="xs" wrap="wrap">
      <Badge size="sm" variant="light" color={templateCategoryColor(category)}>
        {templateCategoryLabel(category, t)}
      </Badge>
      {template.language_code ? (
        <Badge size="sm" variant="light" color="gray">
          {template.language_code}
        </Badge>
      ) : null}
      {template.requires_header_image ? (
        <Badge size="sm" variant="light" color="teal">
          {t("whatsapp-template-header-image")}
        </Badge>
      ) : null}
      {template.body_variable_count > 0 ? (
        <Badge size="sm" variant="outline" color="gray">
          {t("whatsapp-template-variables", {
            count: template.body_variable_count,
          })}
        </Badge>
      ) : null}
    </Group>
  );
}

function WhatsappTemplateCard({
  template,
  onOpen,
}: {
  template: WhatsappTemplate;
  onOpen: (template: WhatsappTemplate) => void;
}) {
  const bodyPreview = (template.body_text || "").trim();

  return (
    <Card
      withBorder
      padding="md"
      radius="md"
      style={{ cursor: "pointer" }}
      onClick={() => onOpen(template)}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
        <Group gap="md" wrap="nowrap" style={{ minWidth: 0, flex: 1 }}>
          <ThemeIcon
            size={40}
            radius="md"
            variant="light"
            color="violet"
            style={{ flexShrink: 0 }}
          >
            <IconTemplate size={22} />
          </ThemeIcon>
          <Stack gap={6} style={{ minWidth: 0, flex: 1 }}>
            <Text fw={700} size="md" lineClamp={1}>
              {template.meta_name}
            </Text>
            <Text size="xs" c="dimmed" ff="monospace">
              {template.template_id}
            </Text>
            <TemplateMetaBadges template={template} />
            {bodyPreview ? (
              <Text size="sm" c="dimmed" lineClamp={2}>
                {bodyPreview}
              </Text>
            ) : null}
          </Stack>
        </Group>
        <IconChevronRight
          size={20}
          style={{ flexShrink: 0, opacity: 0.45, marginTop: 4 }}
        />
      </Group>
    </Card>
  );
}

function WhatsappTemplateModal({
  template,
  opened,
  onClose,
}: {
  template: WhatsappTemplate | null;
  opened: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const variableDescriptions = template?.body_variable_descriptions || [];

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={template?.meta_name || t("whatsapp-templates")}
      size="lg"
    >
      {template ? (
        <Stack gap="md">
          <Text size="xs" c="dimmed" ff="monospace">
            {template.template_id}
          </Text>
          <TemplateMetaBadges template={template} />

          {template.description ? (
            <Text size="sm" c="dimmed">
              {template.description}
            </Text>
          ) : null}

          <WhatsappTemplatePreview template={template} />

          {variableDescriptions.length > 0 ? (
            <Stack gap={4}>
              {variableDescriptions.map((desc, index) => (
                <Text key={`${template.template_id}-var-${index}`} size="sm" c="dimmed">
                  {`{{${index + 1}}}`} {desc}
                </Text>
              ))}
            </Stack>
          ) : null}

        </Stack>
      ) : null}
    </Modal>
  );
}

export default function Whatsapp() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = parseWhatsappPageTab(searchParams.get("tab"));

  const [numbers, setNumbers] = useState<WhatsappLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<WhatsappTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<WhatsappTemplate | null>(
    null
  );
  const [templateOpened, { open: openTemplate, close: closeTemplate }] =
    useDisclosure(false);

  const setActiveTab = (value: string | null) => {
    if (!value) return;
    const next = new URLSearchParams(searchParams);
    if (value === "lines") {
      next.delete("tab");
    } else {
      next.set("tab", value);
    }
    setSearchParams(next, { replace: true });
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setTemplatesLoading(true);
    getWhatsappNumbers()
      .then((res) => {
        if (!cancelled) {
          setNumbers(res as WhatsappLine[]);
          setLoadError(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError(t("whatsapp-load-error"));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    getWhatsappTemplates()
      .then((res) => {
        if (!cancelled) {
          setTemplates(res.templates || []);
          setTemplatesError(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTemplatesError(t("whatsapp-templates-load-error"));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setTemplatesLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  return (
    <AppPage title={t("whatsapp")}>
        <Box px="md" w="100%" maw="48rem" mx="auto">
          <Text ta="center" mb="xs" mt="md">
            {t("whatsapp-intro")}
          </Text>
          <Text ta="center" size="sm" c="dimmed" mb="xl">
            {t("whatsapp-provision-note")}
          </Text>

          <Tabs value={activeTab} onChange={setActiveTab} variant="outline">
            <Tabs.List mb="md">
              <Tabs.Tab
                value="lines"
                leftSection={<IconBrandWhatsapp size={16} />}
              >
                {t("whatsapp-tab-lines")}
              </Tabs.Tab>
              <Tabs.Tab
                value="templates"
                leftSection={<IconTemplate size={16} />}
              >
                {t("whatsapp-tab-templates")}
              </Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="lines">
              <Group justify="space-between" align="baseline" mb="sm">
                <Title order={4}>{t("whatsapp-your-numbers")}</Title>
                {!loading && !loadError ? (
                  <Text size="sm" c="dimmed">
                    {t("whatsapp-lines-count", { count: numbers.length })}
                  </Text>
                ) : null}
              </Group>

              {loading ? (
                <Stack align="center" py="xl">
                  <Loader color="teal" />
                </Stack>
              ) : loadError ? (
                <Text c="red">{loadError}</Text>
              ) : numbers.length === 0 ? (
                <Card withBorder padding="xl" radius="md">
                  <Stack align="center" gap="sm">
                    <ThemeIcon size={48} radius="md" variant="light" color="gray">
                      <IconBrandWhatsapp size={28} />
                    </ThemeIcon>
                    <Text c="dimmed" ta="center">
                      {t("whatsapp-empty-lines")}
                    </Text>
                  </Stack>
                </Card>
              ) : (
                <Stack gap="md">
                  {numbers.map((line) => (
                    <WhatsappLineCard key={line.id} line={line} />
                  ))}
                </Stack>
              )}
            </Tabs.Panel>

            <Tabs.Panel value="templates">
              <Group justify="space-between" align="baseline" mb="xs">
                <Title order={4}>{t("whatsapp-templates")}</Title>
                {!templatesLoading && !templatesError ? (
                  <Text size="sm" c="dimmed">
                    {t("whatsapp-templates-count", { count: templates.length })}
                  </Text>
                ) : null}
              </Group>
              <Text size="sm" c="dimmed" mb="sm">
                {t("whatsapp-templates-intro")}
              </Text>

              {templatesLoading ? (
                <Stack align="center" py="xl">
                  <Loader color="violet" />
                </Stack>
              ) : templatesError ? (
                <Text c="red">{templatesError}</Text>
              ) : templates.length === 0 ? (
                <Card withBorder padding="xl" radius="md">
                  <Stack align="center" gap="sm">
                    <ThemeIcon size={48} radius="md" variant="light" color="gray">
                      <IconTemplate size={28} />
                    </ThemeIcon>
                    <Text c="dimmed" ta="center">
                      {t("whatsapp-templates-empty")}
                    </Text>
                  </Stack>
                </Card>
              ) : (
                <Stack gap="md">
                  {templates.map((template) => (
                    <WhatsappTemplateCard
                      key={template.template_id}
                      template={template}
                      onOpen={(next) => {
                        setSelectedTemplate(next);
                        openTemplate();
                      }}
                    />
                  ))}
                </Stack>
              )}
            </Tabs.Panel>
          </Tabs>

          <WhatsappTemplateModal
            template={selectedTemplate}
            opened={templateOpened}
            onClose={closeTemplate}
          />
        </Box>
    </AppPage>
  );
}
