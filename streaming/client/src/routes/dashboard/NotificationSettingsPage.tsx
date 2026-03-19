import React, { useState, useEffect } from "react";
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
import { DashboardLayout } from "./DashboardLayout";
import {
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
  ActionIcon,
  Select,
} from "@mantine/core";
import { IconPlus, IconTrash } from "@tabler/icons-react";

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
  notify_to_user_id: number | null;
  notify_to_role_id: string | null;
  notify_to_org_id: string | null;
  conditions: TNotificationCondition[];
  enabled: boolean;
}

const EMPTY_FORM: FormData = {
  alert_rule_id: "",
  notify_to_type: "user",
  notify_to_user_id: null,
  notify_to_role_id: null,
  notify_to_org_id: null,
  conditions: [{ ...EMPTY_CONDITION }],
  enabled: true,
};

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

  const handleCreate = () => {
    setEditingRule(null);
    setFormData({
      ...EMPTY_FORM,
      alert_rule_id: alertRules[0]?.id ?? "",
      notify_to_org_id: organization?.id ?? null,
      notify_to_type: "organization",
    });
    setShowForm(true);
  };

  const handleEdit = (rule: TNotificationRule) => {
    setEditingRule(rule);
    const type: NotifyToType = rule.notify_to_user_id
      ? "user"
      : rule.notify_to_role_id
      ? "role"
      : "organization";
    setFormData({
      alert_rule_id: rule.alert_rule_id,
      notify_to_type: type,
      notify_to_user_id: rule.notify_to_user_id,
      notify_to_role_id: rule.notify_to_role_id,
      notify_to_org_id: rule.notify_to_org_id,
      conditions: rule.conditions.length ? rule.conditions : [{ ...EMPTY_CONDITION }],
      enabled: rule.enabled,
    });
    setShowForm(true);
  };

  const handleDelete = async (ruleId: string) => {
    if (!window.confirm(t("confirm-delete") || "Are you sure?")) return;
    try {
      await deleteNotificationRule(ruleId);
      loadAll();
    } catch (err) {
      console.error("Error deleting notification rule:", err);
    }
  };

  const handleSubmit = async () => {
    try {
      const payload = {
        alert_rule_id: formData.alert_rule_id,
        notify_to_user_id: formData.notify_to_type === "user" ? formData.notify_to_user_id : null,
        notify_to_role_id: formData.notify_to_type === "role" ? formData.notify_to_role_id : null,
        notify_to_org_id:
          formData.notify_to_type === "organization" ? formData.notify_to_org_id : null,
        conditions: formData.conditions,
        enabled: formData.enabled,
      };
      if (editingRule) {
        await updateNotificationRule(editingRule.id, payload);
      } else {
        await createNotificationRule(payload as any);
      }
      setShowForm(false);
      setEditingRule(null);
      loadAll();
    } catch (err: any) {
      console.error("Error saving notification rule:", err);
      alert(err.response?.data?.message || t("error-saving") || "Error saving");
    }
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
    setFormData((prev) => ({
      ...prev,
      conditions: prev.conditions.filter((_, i) => i !== index),
    }));

  return (
    <DashboardLayout>
      <Stack gap="lg">
        <Title order={2} ta="center">
          {t("notification-settings") || "Notification Settings"}
        </Title>

        <Group justify="center">
          <Button
            variant="default"
            leftSection={<IconPlus size={16} />}
            onClick={handleCreate}
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
        onClose={() => { setShowForm(false); setEditingRule(null); }}
        title={editingRule ? t("edit-notification-rule") : t("create-notification-rule")}
        size="lg"
        centered
      >
        <Stack gap="md">
          {/* Alert Rule */}
          <NativeSelect
            label={t("alert-rule") || "Alert Rule"}
            value={formData.alert_rule_id}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, alert_rule_id: e.currentTarget.value }))
            }
            data={alertRules.map((r) => ({ value: r.id, label: r.name }))}
            required
          />

          {/* Notify To */}
          <NativeSelect
            label={t("notify-to-type") || "Notify To"}
            value={formData.notify_to_type}
            onChange={(e) => {
              const type = e.currentTarget.value as NotifyToType;
              setFormData((prev) => ({
                ...prev,
                notify_to_type: type,
                notify_to_user_id: null,
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
            <Select
              label={t("select-user") || "Select User"}
              value={formData.notify_to_user_id?.toString() ?? null}
              onChange={(val) =>
                setFormData((prev) => ({
                  ...prev,
                  notify_to_user_id: val ? Number(val) : null,
                }))
              }
              data={members.map((m) => ({
                value: String(m.id),
                label: m.username || m.email || String(m.id),
              }))}
              searchable
              placeholder={t("select-user") || "Select a user"}
            />
          )}

          {formData.notify_to_type === "role" && (
            <Select
              label={t("select-role") || "Select Role"}
              value={formData.notify_to_role_id}
              onChange={(val) =>
                setFormData((prev) => ({ ...prev, notify_to_role_id: val }))
              }
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

          <Divider label={t("conditions") || "Conditions"} labelPosition="center" />

          {formData.conditions.map((cond, i) => (
            <Card key={i} withBorder padding="sm" radius="sm">
              <Stack gap="xs">
                <Group justify="space-between">
                  <Text size="sm" fw={500}>
                    {t("condition") || "Condition"} {i + 1}
                  </Text>
                  {formData.conditions.length > 1 && (
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      size="sm"
                      onClick={() => removeCondition(i)}
                    >
                      <IconTrash size={14} />
                    </ActionIcon>
                  )}
                </Group>

                <TextInput
                  label={t("condition-expression") || "Expression"}
                  placeholder='e.g. "n_alerts > 5"'
                  value={cond.condition}
                  onChange={(e) => updateCondition(i, { condition: e.currentTarget.value })}
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
                  placeholder={t("notification-message-placeholder") || 'e.g. "There are {{n_alerts}} pending alerts!"'}
                  value={cond.message}
                  onChange={(e) => updateCondition(i, { message: e.currentTarget.value })}
                  autosize
                  minRows={2}
                />
              </Stack>
            </Card>
          ))}

          <Button
            variant="subtle"
            size="xs"
            leftSection={<IconPlus size={14} />}
            onClick={addCondition}
          >
            {t("add-condition") || "Add Condition"}
          </Button>

          <Checkbox
            label={t("enabled") || "Enabled"}
            checked={formData.enabled}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, enabled: e.currentTarget.checked }))
            }
          />

          <Divider />
          <Group justify="flex-end" gap="xs">
            <Button variant="default" onClick={() => { setShowForm(false); setEditingRule(null); }}>
              {t("cancel") || "Cancel"}
            </Button>
            <Button onClick={handleSubmit}>
              {editingRule ? t("update") || "Update" : t("create") || "Create"}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </DashboardLayout>
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
          <Button variant="default" size="xs" onClick={() => onEdit(rule)}>
            {t("edit") || "Edit"}
          </Button>
          <Button variant="default" size="xs" color="red" onClick={() => onDelete(rule.id)}>
            {t("delete") || "Delete"}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}
