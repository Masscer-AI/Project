import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Checkbox,
  Divider,
  Group,
  Loader,
  Modal,
  NativeSelect,
  ScrollArea,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconPlus,
  IconRobot,
  IconTemplate,
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

function orgAgents(agents: TAgent[], orgId: string): TAgent[] {
  return agents.filter(
    (a) => a.slug && a.organization && String(a.organization) === orgId
  );
}

export function TemplatesTab({
  agents,
  filterQuery,
}: {
  agents: TAgent[];
  filterQuery: string;
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
    if (!activeTemplate || !orgId) return [];
    const assigned = assignIndex[activeTemplate.id] ?? [];
    return orgAgents(agents, orgId).filter(
      (a) => a.slug && !assigned.some((x) => x.agentSlug === a.slug)
    );
  }, [activeTemplate, orgId, agents, assignIndex]);

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
    async (oid: string, tpls: TDocumentTemplate[]) => {
      const oa = orgAgents(agents, oid);
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
            /* ignore per-agent */
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
        await refreshAssignments(oid, list);
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
    if (!orgId) return;
    void loadTemplates(orgId);
  }, [orgId, loadTemplates]);

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
      <Group align="flex-end" wrap="wrap">
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
      </Group>

      <Text size="sm" c="dimmed">
        {t("templates-tab-description")}
      </Text>

      <Card withBorder p="md">
        <Stack gap="sm">
          <Title order={5}>{t("upload-new-template")}</Title>
          <Group grow align="flex-start" wrap="wrap">
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
          </Group>
          <input
            ref={fileInputRef}
            type="file"
            accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            style={{ display: "none" }}
            onChange={(e) => void handleUpload(e.currentTarget.files)}
          />
          <Button
            leftSection={<IconUpload size={16} />}
            variant="default"
            size="sm"
            loading={uploading}
            disabled={!orgId}
            onClick={() => fileInputRef.current?.click()}
          >
            {t("choose-docx-file")}
          </Button>
          <Text size="xs" c="dimmed">
            {t("templates-jinja-hint")}
          </Text>
        </Stack>
      </Card>

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
        <Stack gap="md">
          {filteredTemplates.map((tpl) => (
            <Card key={tpl.id} withBorder p="md">
              <Group justify="space-between" align="flex-start" wrap="nowrap">
                <Group gap="sm" wrap="nowrap">
                  <IconTemplate size={22} />
                  <div>
                    <Text fw={600}>{tpl.name}</Text>
                    {tpl.description ? (
                      <Text size="sm" c="dimmed">
                        {tpl.description}
                      </Text>
                    ) : null}
                    <Text size="xs" c="dimmed" mt={4}>
                      {tpl.original_filename} · {(tpl.metadata?.placeholders ?? []).length}{" "}
                      {t("placeholders")}
                    </Text>
                  </div>
                </Group>
                <Group gap="xs">
                  <Button size="xs" variant="default" onClick={() => openVariablesModal(tpl)}>
                    {t("edit-variable-descriptions")}
                  </Button>
                  <Button
                    size="xs"
                    variant="default"
                    leftSection={<IconRobot size={14} />}
                    onClick={() => openAssignModal(tpl)}
                  >
                    {t("assign-to-agents")}
                  </Button>
                  <ActionIcon
                    color="red"
                    variant="subtle"
                    onClick={() => openDeleteTemplate(tpl)}
                    aria-label={t("delete-template")}
                  >
                    <IconTrash size={18} />
                  </ActionIcon>
                </Group>
              </Group>

              {(assignIndex[tpl.id] ?? []).length > 0 && (
                <>
                  <Divider my="sm" />
                  <Text size="sm" fw={500}>
                    {t("assigned-agents")}
                  </Text>
                  <Group gap="xs">
                    {(assignIndex[tpl.id] ?? []).map((row) => (
                      <Badge
                        key={row.assignmentId}
                        variant="light"
                        color="violet"
                        rightSection={
                          <ActionIcon
                            size="xs"
                            variant="transparent"
                            color="violet"
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
                </>
              )}
            </Card>
          ))}
        </Stack>
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
