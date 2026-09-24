import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Checkbox,
  Group,
  Loader,
  Menu,
  Modal,
  NativeSelect,
  ScrollArea,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconDots,
  IconPlus,
  IconRobot,
  IconTrash,
  IconUpload,
} from "@tabler/icons-react";
import {
  createAgentTemplateAssignment,
  deleteAgentTemplateAssignment,
  deleteDocumentTemplate,
  getAgentTemplateAssignments,
  getDocumentTemplates,
  getUserOrganizations,
  patchDocumentTemplateVariables,
  uploadDocumentTemplate,
} from "../../modules/apiCalls";
import type {
  TDocumentTemplate,
  TDocumentTemplateVariable,
  TOrganization,
} from "../../types";
import type { TAgent } from "../../types/agents";

type AssignmentRow = {
  assignmentId: string;
  agentSlug: string;
  agentName: string;
};

function agentsWithSlug(agents: TAgent[]): TAgent[] {
  return agents.filter((a) => Boolean(a.slug));
}

export function TemplatesTab({
  agents,
  filterQuery,
  bindUpload,
  onCount,
}: {
  agents: TAgent[];
  filterQuery: string;
  bindUpload?: (fn: () => void) => void;
  onCount?: (count: number) => void;
}) {
  const { t } = useTranslation();
  const [orgs, setOrgs] = useState<TOrganization[]>([]);
  const [orgId, setOrgId] = useState<string | null>(null);
  const [templates, setTemplates] = useState<TDocumentTemplate[]>([]);
  const [loadingOrgs, setLoadingOrgs] = useState(true);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [assignIndex, setAssignIndex] = useState<Record<string, AssignmentRow[]>>(
    {}
  );

  const [uploadName, setUploadName] = useState("");
  const [uploadDescription, setUploadDescription] = useState("");
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const [uploadOpened, uploadHandlers] = useDisclosure(false);
  const [varsModalOpened, varsModalHandlers] = useDisclosure(false);
  const [assignModalOpened, assignModalHandlers] = useDisclosure(false);
  const [deleteModalOpened, deleteModalHandlers] = useDisclosure(false);

  const [activeTemplate, setActiveTemplate] = useState<TDocumentTemplate | null>(
    null
  );
  const [varDraft, setVarDraft] = useState<
    Record<string, TDocumentTemplateVariable>
  >({});

  const [assignAgentSlugs, setAssignAgentSlugs] = useState<string[]>([]);
  const [assignUsage, setAssignUsage] = useState("");

  const assignModalCandidates = useMemo(() => {
    if (!activeTemplate) return [];
    const assigned = assignIndex[activeTemplate.id] ?? [];
    return agentsWithSlug(agents).filter(
      (a) => !assigned.some((x) => x.agentSlug === a.slug)
    );
  }, [activeTemplate, agents, assignIndex]);

  const loadOrgs = useCallback(async () => {
    setLoadingOrgs(true);
    try {
      const list = await getUserOrganizations();
      setOrgs(list);
      if (list.length > 0) {
        setOrgId((prev) => prev ?? list[0].id);
      }
    } catch {
      toast.error(t("error-loading-organizations"));
    } finally {
      setLoadingOrgs(false);
    }
  }, [t]);

  const refreshAssignments = useCallback(
    async (tpls: TDocumentTemplate[]) => {
      const oa = agentsWithSlug(agents);
      const next: Record<string, AssignmentRow[]> = {};
      for (const tpl of tpls) {
        next[tpl.id] = [];
      }
      await Promise.all(
        oa.map(async (ag) => {
          try {
            const { assignments } = await getAgentTemplateAssignments(ag.slug);
            for (const as of assignments) {
              const tid = as.template_id;
              if (!next[tid]) next[tid] = [];
              next[tid].push({
                assignmentId: as.id,
                agentSlug: as.agent_slug,
                agentName: ag.slug === as.agent_slug ? ag.name : as.agent_slug,
              });
            }
          } catch {
          }
        })
      );
      setAssignIndex(next);
    },
    [agents]
  );

  const loadTemplates = useCallback(
    async (oid: string) => {
      setLoadingTemplates(true);
      try {
        const { templates: list } = await getDocumentTemplates(oid);
        setTemplates(list);
        await refreshAssignments(list);
      } catch {
        toast.error(t("error-loading-templates"));
      } finally {
        setLoadingTemplates(false);
      }
    },
    [refreshAssignments, t]
  );

  useEffect(() => {
    void loadOrgs();
  }, [loadOrgs]);

  useEffect(() => {
    onCount?.(templates.length);
  }, [templates.length, onCount]);

  useEffect(() => {
    bindUpload?.(() => uploadHandlers.open());
  }, [bindUpload, uploadHandlers.open]);

  useEffect(() => {
    if (!orgId) return;
    void loadTemplates(orgId);
  }, [orgId, loadTemplates]);

  useEffect(() => {
    if (!orgId || templates.length === 0) return;
    void refreshAssignments(templates);
  }, [orgId, templates, agents, refreshAssignments]);

  const filteredTemplates = useMemo(() => {
    const q = filterQuery.trim().toLowerCase();
    if (!q) return templates;
    return templates.filter(
      (tpl) =>
        tpl.name.toLowerCase().includes(q) ||
        (tpl.description || "").toLowerCase().includes(q) ||
        (tpl.original_filename || "").toLowerCase().includes(q)
    );
  }, [templates, filterQuery]);

  const orgSelectData = useMemo(
    () => orgs.map((o) => ({ value: o.id, label: o.name })),
    [orgs]
  );

  const openVariablesModal = (tpl: TDocumentTemplate) => {
    setActiveTemplate(tpl);
    const vars = tpl.metadata?.variables ?? {};
    const ph = tpl.metadata?.placeholders ?? [];
    const draft: Record<string, TDocumentTemplateVariable> = {};
    for (const key of ph) {
      const v = vars[key];
      draft[key] = {
        description: v?.description ?? "",
        required: v?.required !== false,
        example: v?.example ?? "",
      };
    }
    setVarDraft(draft);
    varsModalHandlers.open();
  };

  const saveVariables = async () => {
    if (!orgId || !activeTemplate) return;
    const toastId = toast.loading(t("saving"));
    try {
      const variables: Record<string, Partial<TDocumentTemplateVariable>> = {};
      for (const [k, v] of Object.entries(varDraft)) {
        variables[k] = {
          description: v.description,
          required: v.required,
          example: v.example,
        };
      }
      const { template } = await patchDocumentTemplateVariables(
        orgId,
        activeTemplate.id,
        variables
      );
      setTemplates((prev) => prev.map((x) => (x.id === template.id ? template : x)));
      toast.success(t("variables-saved"));
      varsModalHandlers.close();
    } catch {
      toast.error(t("error-saving-variables"));
    } finally {
      toast.dismiss(toastId);
    }
  };

  const openAssignModal = (tpl: TDocumentTemplate) => {
    setActiveTemplate(tpl);
    setAssignAgentSlugs([]);
    setAssignUsage("");
    assignModalHandlers.open();
  };

  const submitAssignment = async () => {
    if (!activeTemplate) return;
    const slugSet = new Set(assignModalCandidates.map((a) => a.slug).filter(Boolean));
    const slugsToAssign = assignAgentSlugs.filter((s) => slugSet.has(s));
    if (slugsToAssign.length === 0) {
      toast.error(t("select-at-least-one-agent"));
      return;
    }
    const toastId = toast.loading(t("saving"));
    const templateId = activeTemplate.id;
    const usage = assignUsage;
    try {
      const results = await Promise.allSettled(
        slugsToAssign.map((slug) =>
          createAgentTemplateAssignment(slug, {
            template_id: templateId,
            usage_instructions: usage,
            is_enabled: true,
          })
        )
      );
      const failed = results.filter((r) => r.status === "rejected").length;
      const ok = results.length - failed;
      if (failed === 0) {
        toast.success(t("template-assigned-count", { count: ok }));
        assignModalHandlers.close();
        if (orgId) await loadTemplates(orgId);
      } else if (ok > 0) {
        toast(t("template-assigned-partial", { ok, failed }), { duration: 5000 });
        assignModalHandlers.close();
        if (orgId) await loadTemplates(orgId);
      } else {
        toast.error(t("error-assigning-template"));
      }
    } finally {
      toast.dismiss(toastId);
    }
  };

  const removeAssignment = async (agentSlug: string, assignmentId: string) => {
    const toastId = toast.loading(t("deleting"));
    try {
      await deleteAgentTemplateAssignment(agentSlug, assignmentId);
      toast.success(t("assignment-removed"));
      if (orgId) await loadTemplates(orgId);
    } catch {
      toast.error(t("error-removing-assignment"));
    } finally {
      toast.dismiss(toastId);
    }
  };

  const openDeleteTemplate = (tpl: TDocumentTemplate) => {
    setActiveTemplate(tpl);
    deleteModalHandlers.open();
  };

  const confirmDeleteTemplate = async () => {
    if (!orgId || !activeTemplate) return;
    const toastId = toast.loading(t("deleting"));
    try {
      await deleteDocumentTemplate(orgId, activeTemplate.id);
      toast.success(t("template-deleted"));
      deleteModalHandlers.close();
      await loadTemplates(orgId);
    } catch {
      toast.error(t("error-deleting-template"));
    } finally {
      toast.dismiss(toastId);
    }
  };

  const handleUpload = async (files: FileList | null) => {
    if (!orgId || !files?.length) return;
    const name = uploadName.trim();
    if (!name) {
      toast.error(t("template-name-required"));
      return;
    }
    setUploading(true);
    const toastId = toast.loading(t("uploading-template"));
    try {
      for (const file of Array.from(files)) {
        if (!file.name.toLowerCase().endsWith(".docx")) {
          toast.error(t("template-docx-only"));
          continue;
        }
        const fd = new FormData();
        fd.append("name", name);
        fd.append("description", uploadDescription);
        fd.append("file", file);
        await uploadDocumentTemplate(orgId, fd);
      }
      toast.success(t("template-uploaded"));
      setUploadName("");
      setUploadDescription("");
      uploadHandlers.close();
      await loadTemplates(orgId);
    } catch {
      toast.error(t("error-uploading-template"));
    } finally {
      toast.dismiss(toastId);
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  if (loadingOrgs) {
    return (
      <Stack align="center" py="xl">
        <Loader color="violet" />
      </Stack>
    );
  }

  if (orgs.length === 0) {
    return (
      <Card withBorder p="lg">
        <Text c="dimmed" ta="center">
          {t("templates-no-organization")}
        </Text>
      </Card>
    );
  }

  return (
    <Stack gap="md">
      {orgs.length > 1 && (
        <NativeSelect
          label={t("organization-for-templates")}
          data={orgSelectData}
          value={orgId ?? ""}
          onChange={(e) => {
            const v = e.currentTarget.value;
            setOrgId(v || null);
          }}
          size="sm"
          w={280}
        />
      )}

      <Text size="sm" c="dimmed">
        {t("templates-tab-description")}
      </Text>

      <Modal
        opened={uploadOpened}
        onClose={uploadHandlers.close}
        title={t("upload-new-template")}
      >
        <Stack gap="sm">
          <TextInput
            label={t("template-name")}
            placeholder={t("template-name-placeholder")}
            value={uploadName}
            onChange={(e) => setUploadName(e.currentTarget.value)}
            size="sm"
          />
          <TextInput
            label={t("template-description")}
            placeholder={t("optional")}
            value={uploadDescription}
            onChange={(e) => setUploadDescription(e.currentTarget.value)}
            size="sm"
          />
          <input
            ref={fileInputRef}
            type="file"
            accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            style={{ display: "none" }}
            onChange={(e) => void handleUpload(e.currentTarget.files)}
          />
          <Text size="xs" c="dimmed">
            {t("templates-jinja-hint")}
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={uploadHandlers.close}>
              {t("cancel")}
            </Button>
            <Button
              leftSection={<IconUpload size={16} />}
              loading={uploading}
              disabled={!orgId}
              onClick={() => fileInputRef.current?.click()}
            >
              {t("choose-docx-file")}
            </Button>
          </Group>
        </Stack>
      </Modal>

      {loadingTemplates ? (
        <Stack align="center" py="xl">
          <Loader color="violet" />
        </Stack>
      ) : filteredTemplates.length === 0 ? (
        <Text c="dimmed" ta="center" py="xl">
          {templates.length === 0
            ? t("no-templates-yet")
            : t("no-templates-match")}
        </Text>
      ) : (
        <Table highlightOnHover verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t("kb-col-template")}</Table.Th>
              <Table.Th ta="right">{t("kb-col-placeholders")}</Table.Th>
              <Table.Th>{t("kb-col-agents")}</Table.Th>
              <Table.Th w={48} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {filteredTemplates.map((tpl) => {
              const assigned = assignIndex[tpl.id] ?? [];
              return (
                <Table.Tr key={tpl.id}>
                  <Table.Td>
                    <Group gap="sm" wrap="nowrap">
                      <Box
                        w={36}
                        h={36}
                        style={{
                          borderRadius: 8,
                          background: "var(--mantine-color-blue-light)",
                          color: "var(--mantine-color-blue-6)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 11,
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        DOC
                      </Box>
                      <Box style={{ minWidth: 0 }}>
                        <Text fw={600} lineClamp={1}>
                          {tpl.name}
                        </Text>
                        <Text size="sm" c="dimmed" lineClamp={1}>
                          {tpl.description || tpl.original_filename}
                        </Text>
                      </Box>
                    </Group>
                  </Table.Td>
                  <Table.Td ta="right">
                    {(tpl.metadata?.placeholders ?? []).length}
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4}>
                      {assigned.map((row) => (
                        <Badge
                          key={row.assignmentId}
                          variant="light"
                          color="gray"
                          rightSection={
                            <ActionIcon
                              size="xs"
                              variant="transparent"
                              color="gray"
                              onClick={() =>
                                void removeAssignment(row.agentSlug, row.assignmentId)
                              }
                            >
                              <IconTrash size={12} />
                            </ActionIcon>
                          }
                        >
                          {row.agentName}
                        </Badge>
                      ))}
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <Menu position="bottom-end">
                      <Menu.Target>
                        <ActionIcon variant="subtle" color="gray" aria-label={t("edit")}>
                          <IconDots size={16} />
                        </ActionIcon>
                      </Menu.Target>
                      <Menu.Dropdown>
                        <Menu.Item onClick={() => openVariablesModal(tpl)}>
                          {t("edit-variable-descriptions")}
                        </Menu.Item>
                        <Menu.Item
                          leftSection={<IconRobot size={14} />}
                          onClick={() => openAssignModal(tpl)}
                        >
                          {t("assign-to-agents")}
                        </Menu.Item>
                        <Menu.Item
                          color="red"
                          leftSection={<IconTrash size={14} />}
                          onClick={() => openDeleteTemplate(tpl)}
                        >
                          {t("delete-template")}
                        </Menu.Item>
                      </Menu.Dropdown>
                    </Menu>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}

      <Modal
        opened={varsModalOpened}
        onClose={varsModalHandlers.close}
        title={t("edit-variable-descriptions")}
        size="lg"
      >
        <Stack gap="md">
          {activeTemplate ? (
            <>
              <Text size="sm" c="dimmed">
                {activeTemplate.name}
              </Text>
              {Object.keys(varDraft).length === 0 ? (
                <Text size="sm" c="dimmed">
                  {t("no-placeholders-detected")}
                </Text>
              ) : (
                Object.entries(varDraft).map(([key, spec]) => (
                  <Card key={key} withBorder p="sm">
                    <Text size="sm" fw={600} mb="xs" ff="monospace">
                      {`{{ ${key} }}`}
                    </Text>
                    <TextInput
                      label={t("variable-description")}
                      value={spec.description}
                      onChange={(e) => {
                        const val = e.currentTarget.value;
                        setVarDraft((prev) => ({
                          ...prev,
                          [key]: { ...prev[key], description: val },
                        }));
                      }}
                      size="sm"
                      mb="xs"
                    />
                    <TextInput
                      label={t("variable-example")}
                      value={spec.example}
                      onChange={(e) => {
                        const val = e.currentTarget.value;
                        setVarDraft((prev) => ({
                          ...prev,
                          [key]: { ...prev[key], example: val },
                        }));
                      }}
                      size="sm"
                      mb="xs"
                    />
                    <Checkbox
                      label={t("variable-required")}
                      checked={spec.required}
                      onChange={(e) => {
                        const checked = e.currentTarget.checked;
                        setVarDraft((prev) => ({
                          ...prev,
                          [key]: { ...prev[key], required: checked },
                        }));
                      }}
                    />
                  </Card>
                ))
              )}
              <Button onClick={() => void saveVariables()} disabled={!activeTemplate}>
                {t("save-variables")}
              </Button>
            </>
          ) : null}
        </Stack>
      </Modal>

      <Modal
        opened={assignModalOpened}
        onClose={assignModalHandlers.close}
        title={t("assign-template-to-agents")}
        size="md"
      >
        <Stack gap="md">
          {activeTemplate ? (
            <>
              <Text size="sm" fw={500}>
                {activeTemplate.name}
              </Text>
              {assignModalCandidates.length === 0 ? (
                <Text size="sm" c="dimmed">
                  {t("no-agents-to-assign-template")}
                </Text>
              ) : (
                <Checkbox.Group
                  label={t("select-agents-for-template")}
                  value={assignAgentSlugs}
                  onChange={setAssignAgentSlugs}
                >
                  <ScrollArea.Autosize mah={220} type="auto" offsetScrollbars>
                    <Stack gap="xs" pt={4}>
                      {assignModalCandidates.map((a) => (
                        <Checkbox key={a.slug} value={a.slug!} label={a.name} />
                      ))}
                    </Stack>
                  </ScrollArea.Autosize>
                </Checkbox.Group>
              )}
              <Textarea
                label={t("usage-instructions")}
                placeholder={t("usage-instructions-placeholder")}
                value={assignUsage}
                onChange={(e) => setAssignUsage(e.currentTarget.value)}
                minRows={3}
                size="sm"
              />
              <Button
                leftSection={<IconPlus size={16} />}
                disabled={assignModalCandidates.length === 0}
                onClick={() => void submitAssignment()}
              >
                {t("assign-template")}
              </Button>
            </>
          ) : null}
        </Stack>
      </Modal>

      <Modal
        opened={deleteModalOpened}
        onClose={deleteModalHandlers.close}
        title={t("delete-template")}
        size="sm"
      >
        <Stack gap="md">
          <Text size="sm">
            {t("delete-template-confirm")}{" "}
            <Text span fw={600}>
              {activeTemplate?.name}
            </Text>
            ?
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={deleteModalHandlers.close}>
              {t("cancel")}
            </Button>
            <Button color="red" onClick={() => void confirmDeleteTemplate()}>
              {t("delete")}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
