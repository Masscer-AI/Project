import React, { useState, useEffect, useRef } from "react";
import { useStore } from "../../modules/store";
import {
  getNotificationRules,
  createNotificationRule,
  updateNotificationRule,
  deleteNotificationRule,
  getAlertRules,
  getOrganizationMembers,
  getOrganizationRoles,
  getUserOrganizations,
  buildNotificationRuleDraft,
} from "../../modules/apiCalls";
import {
  TNotificationRule,
  TNotificationCondition,
  TConversationAlertRule,
  TOrganizationMember,
  TOrganizationRole,
  TOrganization,
} from "../../types";
import { useTranslation } from "react-i18next";
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Divider,
  Group,
  Loader,
  Modal,
  NativeSelect,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
  Select,
  MultiSelect,
  ActionIcon,
} from "@mantine/core";
import { IconPlus, IconSparkles, IconTrash } from "@tabler/icons-react";

type NotifyToType = "user" | "role" | "organization";

const EMPTY_CONDITION: TNotificationCondition = {
  subject: "n_alerts",
  condition: "",
  delivery_method: "app",
  message: "",
};

interface FormData {
  alert_rule_id: string;
  notify_to_type: NotifyToType;
  notify_to_user_ids: number[];
  notify_to_role_id: string | null;
  notify_to_org_id: string | null;
  conditions: TNotificationCondition[];
  enabled: boolean;
}

const EMPTY_FORM: FormData = {
  alert_rule_id: "",
  notify_to_type: "organization",
  notify_to_user_ids: [],
  notify_to_role_id: null,
  notify_to_org_id: null,
  conditions: [{ ...EMPTY_CONDITION }],
  enabled: true,
};

function notifyTargetValid(formData: FormData, organization: TOrganization | null): boolean {
  if (formData.notify_to_type === "organization") return !!organization?.id;
  if (formData.notify_to_type === "user") return formData.notify_to_user_ids.length >= 1;
  if (formData.notify_to_type === "role") return !!formData.notify_to_role_id;
  return false;
}

function hasGeneratedConditions(conditions: TNotificationCondition[]): boolean {
  return conditions.some((c) => c.condition.trim() && c.message.trim());
}

function hasPartialConditionContent(conditions: TNotificationCondition[]): boolean {
  return conditions.some((c) => c.condition.trim() || c.message.trim());
}

export default function NotificationSettingsPage() {
  const { startup } = useStore((state) => ({ startup: state.startup }));
  const { t } = useTranslation();

  const [rules, setRules] = useState<TNotificationRule[]>([]);
  const [alertRules, setAlertRules] = useState<TConversationAlertRule[]>([]);
  const [members, setMembers] = useState<TOrganizationMember[]>([]);
  const [roles, setRoles] = useState<TOrganizationRole[]>([]);
  const [organization, setOrganization] = useState<TOrganization | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState<TNotificationRule | null>(null);
  const [formData, setFormData] = useState<FormData>(EMPTY_FORM);

  const [aiPrompt, setAiPrompt] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const saveInFlightRef = useRef(false);
  /** Keeps condition editor visible after AI generate even if user clears fields temporarily. */
  const hasAiFilledConditionsRef = useRef(false);

  useEffect(() => {
    startup();
    loadAll();
  }, [startup]);

  const loadAll = async () => {
    try {
      setIsLoading(true);
      const [rulesData, alertRulesData, orgsData] = await Promise.all([
        getNotificationRules(),
        getAlertRules(),
        getUserOrganizations(),
      ]);
      setRules(rulesData);
      setAlertRules(alertRulesData);

      const org = orgsData[0] ?? null;
      setOrganization(org);

      if (org) {
        const [membersData, rolesData] = await Promise.all([
          getOrganizationMembers(org.id),
          getOrganizationRoles(org.id),
        ]);
        setMembers(membersData);
        setRoles(rolesData);
      }
    } catch (err) {
      console.error("Error loading notification rules:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const enabledAlertRules = alertRules.filter((r) => r.enabled);

  useEffect(() => {
    if (!showForm || editingRule) return;
    if (enabledAlertRules.length === 0) return;
    setFormData((prev) => {
      if (prev.alert_rule_id && enabledAlertRules.some((r) => r.id === prev.alert_rule_id)) {
        return prev;
      }
      return { ...prev, alert_rule_id: enabledAlertRules[0].id };
    });
  }, [showForm, editingRule, alertRules]);

  const targetOk = notifyTargetValid(formData, organization);
  const conditionsOk = hasGeneratedConditions(formData.conditions);
  const canSave = targetOk && conditionsOk;
  const partialConditions = hasPartialConditionContent(formData.conditions);
  const showConditionsEditor =
    formData.conditions.length > 0 &&
    (editingRule != null ||
      conditionsOk ||
      partialConditions ||
      hasAiFilledConditionsRef.current);

  const resetModalAiState = () => {
    setAiPrompt("");
    setAiError(null);
    hasAiFilledConditionsRef.current = false;
  };

  const handleOpenCreate = () => {
    setEditingRule(null);
    setFormData({
      ...EMPTY_FORM,
      alert_rule_id: enabledAlertRules[0]?.id ?? "",
      notify_to_org_id: organization?.id ?? null,
      notify_to_type: "organization",
      conditions: [{ ...EMPTY_CONDITION }],
    });
    resetModalAiState();
    setShowForm(true);
  };

  const updateCondition = (index: number, patch: Partial<TNotificationCondition>) => {
    setFormData((prev) => {
      const updated = [...prev.conditions];
      updated[index] = { ...updated[index], ...patch };
      return { ...prev, conditions: updated };
    });
  };

  const addCondition = () =>
    setFormData((prev) => ({
      ...prev,
      conditions: [...prev.conditions, { ...EMPTY_CONDITION }],
    }));

  const removeCondition = (index: number) =>
    setFormData((prev) => {
      const next = prev.conditions.filter((_, i) => i !== index);
      return {
        ...prev,
        conditions: next.length === 0 ? [{ ...EMPTY_CONDITION }] : next,
      };
    });

  const handleEdit = (rule: TNotificationRule) => {
    hasAiFilledConditionsRef.current = true;
    setEditingRule(rule);
    const type: NotifyToType = rule.notify_to_user_id
      ? "user"
      : rule.notify_to_role_id
        ? "role"
        : "organization";
    setFormData({
      alert_rule_id: rule.alert_rule_id,
      notify_to_type: type,
      notify_to_user_ids: rule.notify_to_user_id ? [rule.notify_to_user_id] : [],
      notify_to_role_id: rule.notify_to_role_id,
      notify_to_org_id: rule.notify_to_org_id,
      conditions: rule.conditions.length ? rule.conditions : [{ ...EMPTY_CONDITION }],
      enabled: rule.enabled,
    });
    resetModalAiState();
    setShowForm(true);
  };

  const handleDelete = async (ruleId: string) => {
    if (!window.confirm(t("confirm-delete-notification-rule") || t("confirm-delete") || "Are you sure?")) return;
    try {
      await deleteNotificationRule(ruleId);
      loadAll();
    } catch (err) {
      console.error("Error deleting notification rule:", err);
    }
  };

  const handleAiGenerate = async () => {
    const prompt = aiPrompt.trim();
    if (!prompt || !formData.alert_rule_id) return;
    setAiError(null);
    setAiLoading(true);
    try {
      const draft = await buildNotificationRuleDraft({
        prompt,
        alert_rule_id: formData.alert_rule_id,
      });
      hasAiFilledConditionsRef.current = true;
      setFormData((prev) => ({
        ...prev,
        alert_rule_id: draft.alert_rule_id,
        conditions:
          draft.conditions?.length > 0
            ? draft.conditions.map((c) => ({
                subject: "n_alerts" as const,
                condition: c.condition,
                delivery_method: c.delivery_method,
                message: c.message,
              }))
            : [{ ...EMPTY_CONDITION }],
      }));
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { error?: string } } };
      setAiError(ax?.response?.data?.error ?? (err instanceof Error ? err.message : "Request failed"));
    } finally {
      setAiLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!canSave) {
      if (!targetOk) {
        alert(t("notification-builder-select-recipients") || "Choose recipients.");
      } else if (!conditionsOk) {
        alert(t("notification-rule-generate-first") || "Generate conditions with the assistant first.");
      }
      return;
    }

    if (saveInFlightRef.current) return;
    saveInFlightRef.current = true;
    setIsSaving(true);

    const common = {
      alert_rule_id: formData.alert_rule_id,
      conditions: formData.conditions,
      enabled: formData.enabled,
    };

    try {
      if (formData.notify_to_type === "user") {
        const ids = [...new Set(formData.notify_to_user_ids)];
        if (ids.length === 0) {
          alert(t("select-at-least-one-user") || "Select at least one user.");
          return;
        }
        if (editingRule) {
          if (ids.length === 1) {
            await updateNotificationRule(editingRule.id, {
              ...common,
              notify_to_user_id: ids[0],
              notify_to_role_id: null,
              notify_to_org_id: null,
            } as any);
          } else {
            await deleteNotificationRule(editingRule.id);
            for (const uid of ids) {
              await createNotificationRule({
                ...common,
                notify_to_user_id: uid,
                notify_to_role_id: null,
                notify_to_org_id: null,
              } as any);
            }
          }
        } else {
          for (const uid of ids) {
            await createNotificationRule({
              ...common,
              notify_to_user_id: uid,
              notify_to_role_id: null,
              notify_to_org_id: null,
            } as any);
          }
        }
      } else {
        const payload = {
          ...common,
          notify_to_user_id: null,
          notify_to_role_id:
            formData.notify_to_type === "role" ? formData.notify_to_role_id : null,
          notify_to_org_id:
            formData.notify_to_type === "organization" ? formData.notify_to_org_id : null,
        };
        if (editingRule) {
          await updateNotificationRule(editingRule.id, payload as any);
        } else {
          await createNotificationRule(payload as any);
        }
      }
      setShowForm(false);
      setEditingRule(null);
      resetModalAiState();
      loadAll();
    } catch (err: any) {
      console.error("Error saving notification rule:", err);
      alert(err.response?.data?.message || t("error-saving") || "Error saving");
    } finally {
      saveInFlightRef.current = false;
      setIsSaving(false);
    }
  };

  const closeModal = () => {
    setShowForm(false);
    setEditingRule(null);
    resetModalAiState();
  };

  return (
    <>
      <Stack gap="lg" align="stretch">
        <Title order={2} ta="center">
          {t("notification-settings") || "Notification Settings"}
        </Title>

        <Group justify="center">
          <Button
            type="button"
            leftSection={<IconPlus size={16} />}
            onClick={handleOpenCreate}
            disabled={alertRules.length === 0}
          >
            {t("create-notification-rule") || "New Notification Rule"}
          </Button>
        </Group>

        {isLoading ? (
          <Group justify="center" py="xl">
            <Loader />
          </Group>
        ) : rules.length === 0 ? (
          <Text ta="center" c="dimmed" py="xl" size="lg">
            {t("no-notification-rules-found") || "No notification rules yet. Create your first one!"}
          </Text>
        ) : (
          <SimpleGrid cols={{ base: 1, md: 2, lg: 3 }} spacing="md">
            {rules.map((rule) => (
              <NotificationRuleCard
                key={rule.id}
                rule={rule}
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
        onClose={closeModal}
        title={
          <Group gap="xs">
            <IconSparkles size={20} />
            <span>{editingRule ? t("edit-notification-rule") : t("create-notification-rule")}</span>
          </Group>
        }
        size="lg"
        centered
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            {t("notification-rule-modal-ai-only-hint") ||
              "Choose the alert rule and recipients, describe when to notify in your own words, then generate. Conditions are created by the assistant."}
          </Text>

          <NativeSelect
            label={t("select-alert-rule-required") || "Alert rule"}
            value={formData.alert_rule_id}
            onChange={(e) => setFormData((prev) => ({ ...prev, alert_rule_id: e.currentTarget.value }))}
            data={enabledAlertRules.map((r) => ({ value: r.id, label: r.name }))}
            disabled={enabledAlertRules.length === 0}
            required
          />

          <Divider label={t("notification-builder-who-to-notify") || "Recipients"} labelPosition="center" />

          <NativeSelect
            label={t("notify-to-type") || "Notify To"}
            value={formData.notify_to_type}
            onChange={(e) => {
              const type = e.currentTarget.value as NotifyToType;
              setFormData((prev) => ({
                ...prev,
                notify_to_type: type,
                notify_to_user_ids: [],
                notify_to_role_id: null,
                notify_to_org_id: type === "organization" ? (organization?.id ?? null) : null,
              }));
            }}
            data={[
              { value: "user", label: t("user") || "User" },
              { value: "role", label: t("role") || "Role" },
              { value: "organization", label: t("organization") || "Organization" },
            ]}
          />

          {formData.notify_to_type === "user" && (
            <Stack gap="xs">
              <MultiSelect
                label={t("select-users") || "Select users"}
                value={formData.notify_to_user_ids.map(String)}
                onChange={(vals) =>
                  setFormData((prev) => ({
                    ...prev,
                    notify_to_user_ids: vals.map((v) => Number(v)),
                  }))
                }
                data={members.map((m) => ({
                  value: String(m.id),
                  label: m.username || m.email || String(m.id),
                }))}
                searchable
                placeholder={t("select-users-placeholder") || "One or more users"}
              />
              {editingRule && formData.notify_to_user_ids.length > 1 && (
                <Text size="xs" c="dimmed">
                  {t("notification-rule-multi-user-edit-hint") ||
                    "Saving will replace this rule with one per selected user."}
                </Text>
              )}
            </Stack>
          )}

          {formData.notify_to_type === "role" && (
            <Select
              label={t("select-role") || "Select Role"}
              value={formData.notify_to_role_id}
              onChange={(val) => setFormData((prev) => ({ ...prev, notify_to_role_id: val }))}
              data={roles.map((r) => ({ value: r.id, label: r.name }))}
              searchable
              placeholder={t("select-role") || "Select a role"}
            />
          )}

          {formData.notify_to_type === "organization" && (
            <TextInput
              label={t("organization") || "Organization"}
              value={organization?.name ?? ""}
              disabled
            />
          )}

          <Divider
            label={
              <Group gap={6}>
                <IconSparkles size={14} />
                {t("notification-rule-ai-section") || "Conditions (assistant)"}
              </Group>
            }
            labelPosition="center"
          />

          <Textarea
            label={t("describe-notification") || "What should we notify you about?"}
            description={
              t("notification-builder-prompt-description") ||
              "You can also say if you want delivery in the app only, email only, or all channels."
            }
            placeholder={
              t("notification-builder-placeholder") ||
              'Example: "Notify me when there are 5 or more pending problems for the billing alert."'
            }
            value={aiPrompt}
            onChange={(e) => setAiPrompt(e.currentTarget.value)}
            minRows={3}
            autosize
          />

          {aiError && (
            <Text size="sm" c="red">
              {aiError}
            </Text>
          )}

          <Group>
            <Button
              type="button"
              leftSection={<IconSparkles size={16} />}
              variant="light"
              onClick={handleAiGenerate}
              loading={aiLoading}
              disabled={
                !aiPrompt.trim() ||
                !formData.alert_rule_id ||
                enabledAlertRules.length === 0
              }
            >
              {t("generate-suggestion") || "Generate conditions"}
            </Button>
          </Group>

          {showConditionsEditor && (
            <Stack gap="md">
              <Divider label={t("conditions") || "Conditions"} labelPosition="center" />
              <Text size="xs" c="dimmed">
                {t("notification-conditions-edit-hint") ||
                  "Edit or remove what the assistant generated, or add more conditions."}
              </Text>
              {formData.conditions.map((cond, i) => (
                <Card key={i} withBorder padding="sm" radius="sm">
                  <Stack gap="xs">
                    <Group justify="space-between" wrap="nowrap" gap="xs">
                      <Text size="sm" fw={500}>
                        {t("condition") || "Condition"} {i + 1}
                      </Text>
                      <ActionIcon
                        type="button"
                        variant="subtle"
                        color="red"
                        size="sm"
                        onClick={() => removeCondition(i)}
                        aria-label={t("remove-condition") || "Remove condition"}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>

                    <TextInput
                      label={t("condition-expression") || "Expression"}
                      placeholder='e.g. n_alerts > 5'
                      value={cond.condition}
                      onChange={(e) => updateCondition(i, { condition: e.currentTarget.value })}
                      styles={{ input: { fontFamily: "monospace" } }}
                    />

                    <NativeSelect
                      label={t("delivery-method") || "Delivery Method"}
                      value={cond.delivery_method}
                      onChange={(e) =>
                        updateCondition(i, {
                          delivery_method: e.currentTarget.value as TNotificationCondition["delivery_method"],
                        })
                      }
                      data={[
                        { value: "app", label: t("in-app") || "In-App" },
                        { value: "email", label: t("email") || "Email" },
                        { value: "all", label: t("all-channels") || "All Channels" },
                      ]}
                    />

                    <Textarea
                      label={t("message") || "Message"}
                      placeholder={
                        t("notification-message-placeholder") ||
                        'e.g. "There are {{n_alerts}} pending alerts!"'
                      }
                      value={cond.message}
                      onChange={(e) => updateCondition(i, { message: e.currentTarget.value })}
                      autosize
                      minRows={2}
                    />
                  </Stack>
                </Card>
              ))}

              <Button
                type="button"
                variant="subtle"
                size="xs"
                leftSection={<IconPlus size={14} />}
                onClick={addCondition}
              >
                {t("add-condition") || "Add condition"}
              </Button>
            </Stack>
          )}

          {!targetOk && (
            <Alert color="orange" variant="light" title={t("notification-builder-recipients-missing-title")}>
              {t("notification-builder-select-recipients")}
            </Alert>
          )}

          {targetOk && !conditionsOk && (
            <Text size="sm" c="dimmed">
              {t("notification-rule-generate-first-hint") ||
                "Use “Generate conditions” to create the rule from your description."}
            </Text>
          )}

          <Checkbox
            label={t("enabled") || "Enabled"}
            checked={formData.enabled}
            onChange={(e) => setFormData((prev) => ({ ...prev, enabled: e.currentTarget.checked }))}
          />

          <Divider />
          <Group justify="flex-end" gap="xs">
            <Button type="button" variant="default" onClick={closeModal} disabled={isSaving}>
              {t("cancel") || "Cancel"}
            </Button>
            <Button
              type="button"
              onClick={handleSubmit}
              disabled={!canSave || isSaving}
              loading={isSaving}
            >
              {editingRule ? t("update") || "Update" : t("create") || "Create"}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}

function NotificationRuleCard({
  rule,
  onEdit,
  onDelete,
  t,
}: {
  rule: TNotificationRule;
  onEdit: (rule: TNotificationRule) => void;
  onDelete: (ruleId: string) => void;
  t: any;
}) {
  const targetLabel =
    rule.notify_to_user_username ??
    rule.notify_to_role_name ??
    rule.notify_to_org_name ??
    "—";

  return (
    <Card withBorder padding="lg" radius="md">
      <Stack gap="sm">
        <Group justify="space-between" wrap="wrap">
          <Text fw={600} size="sm">
            {rule.alert_rule_name ?? rule.alert_rule_id}
          </Text>
          <Badge color={rule.enabled ? "green" : "red"} size="sm">
            {rule.enabled ? t("enabled") || "Enabled" : t("disabled") || "Disabled"}
          </Badge>
        </Group>

        <Text size="xs" c="dimmed">
          {t("notify-to") || "Notify to"}: {targetLabel}
        </Text>

        <Text size="xs" c="dimmed">
          {t("conditions") || "Conditions"}: {rule.conditions.length}
        </Text>

        {rule.conditions.map((cond, i) => (
          <Text key={i} size="xs" c="dimmed" lineClamp={1}>
            · {cond.condition} → {cond.delivery_method}
          </Text>
        ))}

        <Divider />

        <Group gap="xs">
          <Button type="button" variant="default" size="xs" onClick={() => onEdit(rule)}>
            {t("edit") || "Edit"}
          </Button>
          <Button type="button" variant="default" size="xs" color="red" onClick={() => onDelete(rule.id)}>
            {t("delete") || "Delete"}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}
