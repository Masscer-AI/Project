import React, { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  Button,
  Card,
  Divider,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
  Title,
  UnstyledButton,
} from "@mantine/core";
import {
  IconArrowLeft,
  IconBrandGoogleDrive,
  IconChevronRight,
  IconPlugConnected,
  IconRefresh,
} from "@tabler/icons-react";
import {
  getIntegrations,
  importDriveFile,
  IntegrationOwnerType,
  listDriveFiles,
  TDriveFile,
  TIntegration,
} from "../../modules/apiCalls";
import { useStore } from "../../modules/store";
import { TAttachment, TDocument } from "../../types";

const GOOGLE_DRIVE = "google_drive";

type Props = {
  opened: boolean;
  onClose: () => void;
  onImported?: (document: TDocument) => void;
};

type Step = "accounts" | "files";

export function attachDocumentToChat(
  document: TDocument,
  addAttachment: (attachment: TAttachment, replace?: boolean) => void
) {
  const attachment: TAttachment = {
    content: document.text,
    name: document.name,
    type: document.content_type || "text/plain",
    id: document.id,
    mode: "all_possible_text",
    text: document.text,
  };
  addAttachment(attachment, true);
}

function AccountRow({
  integration,
  onSelect,
}: {
  integration: TIntegration;
  onSelect: () => void;
}) {
  const label =
    integration.account_email ||
    integration.account_label ||
    integration.owner_label;

  return (
    <UnstyledButton onClick={onSelect} w="100%">
      <Card
        withBorder
        padding="sm"
        radius="md"
        style={{ cursor: "pointer" }}
      >
        <Group justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
            <IconBrandGoogleDrive size={20} />
            <Stack gap={0} style={{ minWidth: 0 }}>
              <Text fw={500} truncate>
                {label}
              </Text>
              {integration.account_label &&
                integration.account_email &&
                integration.account_label !== integration.account_email && (
                  <Text size="xs" c="dimmed" truncate>
                    {integration.account_label}
                  </Text>
                )}
            </Stack>
          </Group>
          <IconChevronRight size={18} style={{ opacity: 0.5 }} />
        </Group>
      </Card>
    </UnstyledButton>
  );
}

export function DriveFilePicker({ opened, onClose, onImported }: Props) {
  const { t } = useTranslation();
  const addAttachment = useStore((s) => s.addAttachment);

  const [step, setStep] = useState<Step>("accounts");
  const [integrations, setIntegrations] = useState<TIntegration[]>([]);
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [selectedOwner, setSelectedOwner] = useState<IntegrationOwnerType | null>(
    null
  );
  const [selectedAccountLabel, setSelectedAccountLabel] = useState("");
  const [files, setFiles] = useState<TDriveFile[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [importingId, setImportingId] = useState<string | null>(null);

  const personalAccounts = useMemo(
    () =>
      integrations.filter(
        (i) =>
          i.provider === GOOGLE_DRIVE &&
          i.owner_type === "user" &&
          i.connected
      ),
    [integrations]
  );

  const organizationAccounts = useMemo(
    () =>
      integrations.filter(
        (i) =>
          i.provider === GOOGLE_DRIVE &&
          i.owner_type === "organization" &&
          i.connected
      ),
    [integrations]
  );

  const hasAnyAccount =
    personalAccounts.length > 0 || organizationAccounts.length > 0;

  const resetState = () => {
    setStep("accounts");
    setSelectedOwner(null);
    setSelectedAccountLabel("");
    setFiles([]);
    setImportingId(null);
  };

  const loadAccounts = useCallback(async () => {
    setLoadingAccounts(true);
    try {
      const data = await getIntegrations();
      setIntegrations(data.integrations || []);
    } catch {
      toast.error(t("an-error-occurred"));
      setIntegrations([]);
    } finally {
      setLoadingAccounts(false);
    }
  }, [t]);

  const loadFiles = useCallback(
    async (owner: IntegrationOwnerType) => {
      setLoadingFiles(true);
      try {
        const fileData = await listDriveFiles(owner, 50);
        setFiles(fileData.files || []);
      } catch (err: unknown) {
        const msg =
          (err as { response?: { data?: { error?: string } } })?.response?.data
            ?.error || t("an-error-occurred");
        toast.error(msg);
        setFiles([]);
      } finally {
        setLoadingFiles(false);
      }
    },
    [t]
  );

  useEffect(() => {
    if (opened) {
      resetState();
      loadAccounts();
    }
  }, [opened, loadAccounts]);

  const handleSelectAccount = (integration: TIntegration) => {
    const owner = integration.owner_type;
    const label =
      integration.account_email ||
      integration.account_label ||
      integration.owner_label;
    setSelectedOwner(owner);
    setSelectedAccountLabel(label);
    setStep("files");
    loadFiles(owner);
  };

  const handleBack = () => {
    setStep("accounts");
    setSelectedOwner(null);
    setSelectedAccountLabel("");
    setFiles([]);
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  const handleImport = async (file: TDriveFile) => {
    if (!selectedOwner) return;
    setImportingId(file.id);
    try {
      const result = await importDriveFile(file.id, selectedOwner);
      const doc = result.document;
      attachDocumentToChat(doc, addAttachment);
      onImported?.(doc);
      toast.success(
        result.created
          ? t("drive-import-success")
          : t("drive-import-updated")
      );
      handleClose();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: string } } })?.response?.data
          ?.error || t("drive-import-error");
      toast.error(msg);
    } finally {
      setImportingId(null);
    }
  };

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      title={
        <Group gap="xs">
          <IconBrandGoogleDrive size={22} />
          <Title order={4}>{t("drive-import-title")}</Title>
        </Group>
      }
      size="lg"
      centered
      overlayProps={{ backgroundOpacity: 0.55, blur: 3 }}
    >
      <Stack gap="md">
        {step === "accounts" && (
          <>
            <Text size="sm" c="dimmed">
              {t("drive-import-select-account")}
            </Text>

            {loadingAccounts && (
              <Stack align="center" py="xl">
                <Loader color="violet" />
              </Stack>
            )}

            {!loadingAccounts && !hasAnyAccount && (
              <Stack align="center" gap="md" py="lg">
                <Text c="dimmed" ta="center">
                  {t("drive-import-no-accounts")}
                </Text>
                <Button
                  component={Link}
                  to="/integrations"
                  variant="light"
                  leftSection={<IconPlugConnected size={18} />}
                  onClick={handleClose}
                >
                  {t("integrations-title")}
                </Button>
              </Stack>
            )}

            {!loadingAccounts && personalAccounts.length > 0 && (
              <Stack gap="xs">
                <Text size="sm" fw={600}>
                  {t("drive-import-personal-accounts")}
                </Text>
                {personalAccounts.map((integration) => (
                  <AccountRow
                    key={integration.id}
                    integration={integration}
                    onSelect={() => handleSelectAccount(integration)}
                  />
                ))}
              </Stack>
            )}

            {!loadingAccounts &&
              personalAccounts.length > 0 &&
              organizationAccounts.length > 0 && <Divider />}

            {!loadingAccounts && organizationAccounts.length > 0 && (
              <Stack gap="xs">
                <Text size="sm" fw={600}>
                  {t("drive-import-organization-accounts")}
                </Text>
                {organizationAccounts.map((integration) => (
                  <AccountRow
                    key={integration.id}
                    integration={integration}
                    onSelect={() => handleSelectAccount(integration)}
                  />
                ))}
              </Stack>
            )}
          </>
        )}

        {step === "files" && selectedOwner && (
          <>
            <Group justify="space-between" wrap="nowrap">
              <Button
                variant="subtle"
                size="compact-sm"
                leftSection={<IconArrowLeft size={16} />}
                onClick={handleBack}
              >
                {t("drive-import-back-to-accounts")}
              </Button>
              <Button
                variant="subtle"
                size="compact-sm"
                leftSection={<IconRefresh size={14} />}
                onClick={() => loadFiles(selectedOwner)}
                loading={loadingFiles}
              >
                {t("refresh")}
              </Button>
            </Group>

            <Text size="sm" c="dimmed">
              {t("drive-import-files-for", { account: selectedAccountLabel })}
            </Text>

            {loadingFiles && (
              <Stack align="center" py="xl">
                <Loader color="violet" />
                <Text size="sm" c="dimmed">
                  {t("drive-import-loading")}
                </Text>
              </Stack>
            )}

            {!loadingFiles && files.length === 0 && (
              <Text c="dimmed" ta="center" py="xl">
                {t("drive-import-empty")}
              </Text>
            )}

            {!loadingFiles &&
              files.map((file) => (
                <Group
                  key={file.id}
                  justify="space-between"
                  wrap="nowrap"
                  p="sm"
                  style={{
                    border: "1px solid var(--mantine-color-dark-4)",
                    borderRadius: 8,
                  }}
                >
                  <Stack gap={2} style={{ minWidth: 0 }}>
                    <Text fw={500} truncate>
                      {file.name}
                    </Text>
                    <Text size="xs" c="dimmed" truncate>
                      {file.mimeType}
                    </Text>
                  </Stack>
                  <Button
                    size="xs"
                    loading={importingId === file.id}
                    onClick={() => handleImport(file)}
                  >
                    {t("drive-import-action")}
                  </Button>
                </Group>
              ))}
          </>
        )}
      </Stack>
    </Modal>
  );
}
