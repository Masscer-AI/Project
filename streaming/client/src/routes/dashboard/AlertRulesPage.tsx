import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import {
  getAlertRules,
  createAlertRule,
  updateAlertRule,
  deleteAlertRule,
} from "../../modules/apiCalls";
import { TConversationAlertRule } from "../../types";
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
    notify_to: "all_staff" as "all_staff" | "selected_members",
  });

  useEffect(() => {
    startup();
    loadAlertRules();
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
      notify_to: "all_staff",
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
      notify_to: rule.notify_to,
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

  const handleSubmit = async () => {
    try {
      if (editingRule) {
        await updateAlertRule(editingRule.id, formData);
      } else {
        await createAlertRule(formData);
      }
      setShowForm(false);
      setEditingRule(null);
      loadAlertRules();
    } catch (error: any) {
      console.error("Error saving alert rule:", error);
      alert(
        error.response?.data?.message ||
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
    <DashboardLayout>
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
                onEdit={handleEdit}
                onDelete={handleDelete}
                t={t}
              />
            ))}
          </SimpleGrid>
        )}
      </Stack>

      {/* Create/Edit Modal */}
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
              setFormData((prev) => ({ ...prev, scope: val }));
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
          <NativeSelect
            label={t("notify-to")}
            value={formData.notify_to}
            onChange={(e) => {
              const val = e.currentTarget.value as
                | "all_staff"
                | "selected_members";
              setFormData((prev) => ({ ...prev, notify_to: val }));
            }}
            data={[
              { value: "all_staff", label: t("all-staff") },
              {
                value: "selected_members",
                label: t("selected-members"),
              },
            ]}
          />
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
    </DashboardLayout>
  );
}

function AlertRuleCard({
  rule,
  onEdit,
  onDelete,
  t,
}: {
  rule: TConversationAlertRule;
  onEdit: (rule: TConversationAlertRule) => void;
  onDelete: (ruleId: string) => void;
  t: any;
}) {
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
          <Text size="xs" c="dimmed">
            {t("notify-to") || "Notify To"}:{" "}
            {rule.notify_to === "all_staff"
              ? t("all-staff") || "All Staff"
              : t("selected-members") || "Selected Members"}
          </Text>
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
