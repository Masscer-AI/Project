import React, { useState, useEffect, useMemo } from "react";
import { useStore } from "../../modules/store";
import {
  getAlertRules,
  createAlertRule,
  updateAlertRule,
  deleteAlertRule,
  getAgents,
  getUserOrganizations,
} from "../../modules/apiCalls";
import { TConversationAlertRule, TOrganization } from "../../types";
import { TAgent } from "../../types/agents";
import { useTranslation } from "react-i18next";
import {
  Badge,
  Button,
  Card,
  Checkbox,
  Divider,
  Group,
  Loader,
  Modal,
  MultiSelect,
  NativeSelect,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { IconPlus } from "@tabler/icons-react";

export default function AlertRulesPage() {
  const { startup } = useStore((state) => ({
    startup: state.startup,
  }));
  const { t } = useTranslation();
  const [alertRules, setAlertRules] = useState<TConversationAlertRule[]>([]);
  const [organization, setOrganization] = useState<TOrganization | null>(null);
  const [orgAgents, setOrgAgents] = useState<TAgent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState<TConversationAlertRule | null>(
    null
  );
  const [formData, setFormData] = useState({
    name: "",
    trigger: "",
    extractions: {} as Record<string, any>,
    scope: "all_conversations" as "all_conversations" | "selected_agents",
    enabled: true,
    agent_ids: [] as number[],
  });

  const agentOptions = useMemo(
    () =>
      orgAgents
        .filter((a) => a.id != null)
        .map((a) => ({ value: String(a.id), label: a.name })),
    [orgAgents]
  );

  useEffect(() => {
    startup();
    loadAlertRules();
    (async () => {
      try {
        const [orgs, agentsRes] = await Promise.all([
          getUserOrganizations(),
          getAgents(),
        ]);
        const org = orgs[0] ?? null;
        setOrganization(org);
        const orgId = org?.id;
        const list = agentsRes.agents ?? [];
        setOrgAgents(
          orgId
            ? list.filter(
                (a: TAgent) =>
                  a.organization != null &&
                  String(a.organization) === String(orgId)
              )
            : []
        );
      } catch (e) {
        console.error("Error loading org agents:", e);
      }
    })();
  }, [startup]);

  const loadAlertRules = async () => {
    try {
      setIsLoading(true);
      const data = await getAlertRules();
      setAlertRules(data);
    } catch (error) {
      console.error("Error loading alert rules:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingRule(null);
    setFormData({
      name: "",
      trigger: "",
      extractions: {},
      scope: "all_conversations",
      enabled: true,
      agent_ids: [],
    });
    setShowForm(true);
  };

  const handleEdit = (rule: TConversationAlertRule) => {
    setEditingRule(rule);
    setFormData({
      name: rule.name,
      trigger: rule.trigger,
      extractions: rule.extractions || {},
      scope: rule.scope,
      enabled: rule.enabled,
      agent_ids: Array.isArray(rule.agent_ids) ? [...rule.agent_ids] : [],
    });
    setShowForm(true);
  };

  const handleDelete = async (ruleId: string) => {
    if (
      !window.confirm(
        t("confirm-delete-alert-rule") ||
          "Are you sure you want to delete this alert rule?"
      )
    ) {
      return;
    }
    try {
      await deleteAlertRule(ruleId);
      loadAlertRules();
    } catch (error) {
      console.error("Error deleting alert rule:", error);
      alert(t("error-deleting-alert-rule") || "Error deleting alert rule");
    }
  };

  const buildPayload = () => {
    const agent_ids =
      formData.scope === "selected_agents" ? formData.agent_ids : [];
    return {
      name: formData.name,
      trigger: formData.trigger,
      extractions: formData.extractions,
      scope: formData.scope,
      enabled: formData.enabled,
      agent_ids,
    };
  };

  const handleSubmit = async () => {
    if (formData.scope === "selected_agents" && formData.agent_ids.length === 0) {
      alert(
        t("alert-rule-agents-required") ||
          "Select at least one agent when using selected agents scope."
      );
      return;
    }
    try {
      const payload = buildPayload();
      if (editingRule) {
        await updateAlertRule(editingRule.id, payload);
      } else {
        await createAlertRule(payload);
      }
      setShowForm(false);
      setEditingRule(null);
      loadAlertRules();
    } catch (error: any) {
      console.error("Error saving alert rule:", error);
      const errMsg =
        error.response?.data?.errors?.agent_ids?.[0] ||
        error.response?.data?.message;
      alert(
        errMsg ||
          t("error-saving-alert-rule") ||
          "Error saving alert rule"
      );
    }
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingRule(null);
  };

  return (
    <>
      <Stack gap="lg">
        <Title order={2} ta="center">
          {t("alert-rules") || "Alert Rules"}
        </Title>

        <Group justify="center">
          <Button
            variant="default"
            leftSection={<IconPlus size={16} />}
            onClick={handleCreate}
          >
            {t("create-alert-rule") || "+ New Rule"}
          </Button>
        </Group>

        {isLoading ? (
          <Group justify="center" py="xl">
            <Loader />
          </Group>
        ) : alertRules.length === 0 ? (
          <Text ta="center" c="dimmed" py="xl" size="lg">
            {t("no-alert-rules-found") ||
              "No alert rules found. Create your first one!"}
          </Text>
        ) : (
          <SimpleGrid cols={{ base: 1, md: 2, lg: 3 }} spacing="md">
            {alertRules.map((rule) => (
              <AlertRuleCard
                key={rule.id}
                rule={rule}
                orgAgents={orgAgents}
                onEdit={handleEdit}
                onDelete={handleDelete}
                t={t}
              />
            ))}
          </SimpleGrid>
        )}
      </Stack>

      <Modal
        opened={showForm}
        onClose={handleCancel}
        title={editingRule ? t("edit-alert-rule") : t("create-alert-rule")}
        size="lg"
        centered
      >
        <Stack gap="md">
          <TextInput
            label={t("name")}
            value={formData.name}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setFormData((prev) => ({ ...prev, name: val }));
            }}
            required
          />
          <Textarea
            label={t("trigger")}
            value={formData.trigger}
            onChange={(e) => {
              const val = e.currentTarget.value;
              setFormData((prev) => ({ ...prev, trigger: val }));
            }}
            required
            autosize
            minRows={3}
            placeholder={t("trigger-description-placeholder")}
          />
          <NativeSelect
            label={t("scope")}
            value={formData.scope}
            onChange={(e) => {
              const val = e.currentTarget.value as
                | "all_conversations"
                | "selected_agents";
              setFormData((prev) => ({
                ...prev,
                scope: val,
                agent_ids: val === "all_conversations" ? [] : prev.agent_ids,
              }));
            }}
            data={[
              {
                value: "all_conversations",
                label: t("all-conversations"),
              },
              {
                value: "selected_agents",
                label: t("selected-agents"),
              },
            ]}
          />
          {formData.scope === "selected_agents" && (
            <MultiSelect
              label={t("alert-rule-agents-label") || "Agents"}
              placeholder={t("alert-rule-agents-placeholder") || "Choose agents"}
              data={agentOptions}
              value={formData.agent_ids.map(String)}
              onChange={(vals) =>
                setFormData((prev) => ({
                  ...prev,
                  agent_ids: vals.map((v) => Number(v)),
                }))
              }
              searchable
              nothingFoundMessage={t("multiselect-no-matches") || "No matches"}
              disabled={!organization || orgAgents.length === 0}
            />
          )}
          {formData.scope === "selected_agents" &&
            organization &&
            orgAgents.length === 0 && (
              <Text size="sm" c="dimmed">
                {t("alert-rule-no-org-agents") ||
                  "No agents belong to this organization yet. Create org agents first."}
              </Text>
            )}
          <Checkbox
            label={t("enabled")}
            checked={formData.enabled}
            onChange={(e) => {
              const checked = e.currentTarget.checked;
              setFormData((prev) => ({ ...prev, enabled: checked }));
            }}
          />
          <Divider />
          <Group justify="flex-end" gap="xs">
            <Button variant="default" onClick={handleCancel}>
              {t("cancel")}
            </Button>
            <Button onClick={handleSubmit}>
              {editingRule ? t("update") : t("create")}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}

function AlertRuleCard({
  rule,
  orgAgents,
  onEdit,
  onDelete,
  t,
}: {
  rule: TConversationAlertRule;
  orgAgents: TAgent[];
  onEdit: (rule: TConversationAlertRule) => void;
  onDelete: (ruleId: string) => void;
  t: any;
}) {
  const agentNames = useMemo(() => {
    if (rule.scope !== "selected_agents" || !rule.agent_ids?.length) return [];
    const byId = new Map(orgAgents.filter((a) => a.id != null).map((a) => [a.id!, a.name]));
    return rule.agent_ids.map((id) => byId.get(id) ?? `#${id}`);
  }, [rule.scope, rule.agent_ids, orgAgents]);

  return (
    <Card withBorder padding="lg" radius="md">
      <Stack gap="sm">
        <Group justify="space-between" wrap="wrap">
          <Text fw={600}>{rule.name}</Text>
          <Badge color={rule.enabled ? "green" : "red"} size="sm">
            {rule.enabled
              ? t("enabled") || "Enabled"
              : t("disabled") || "Disabled"}
          </Badge>
        </Group>

        <Text size="sm" c="dimmed" lineClamp={3}>
          {rule.trigger}
        </Text>

        <Stack gap={4}>
          <Text size="xs" c="dimmed">
            {t("scope") || "Scope"}:{" "}
            {rule.scope === "all_conversations"
              ? t("all-conversations") || "All Conversations"
              : t("selected-agents") || "Selected Agents"}
          </Text>
          {rule.scope === "selected_agents" && agentNames.length > 0 && (
            <Text size="xs" c="dimmed">
              {t("alert-rule-agents-summary") || "Agents"}:{" "}
              {agentNames.join(", ")}
            </Text>
          )}
        </Stack>

        <Divider />

        <Group gap="xs">
          <Button variant="default" size="xs" onClick={() => onEdit(rule)}>
            {t("edit") || "Edit"}
          </Button>
          <Button
            variant="default"
            size="xs"
            color="red"
            onClick={() => onDelete(rule.id)}
          >
            {t("delete") || "Delete"}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}
