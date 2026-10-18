import React, { useEffect, useState } from "react";
import { useLoaderData } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button, Group, Paper, Stack, Text } from "@mantine/core";
import { IconDownload, IconFile } from "@tabler/icons-react";

import {
  fileShareDownloadURL,
  getFileShare,
  TFileShare,
} from "../../modules/apiCalls";
import { useStore } from "../../modules/store";

const REFRESH_AFTER_DOWNLOAD_MS = 1500;

export default function FileSharePage() {
  const loaderData = useLoaderData() as TFileShare | null;
  const { t, i18n } = useTranslation();
  const [share, setShare] = useState<TFileShare | null>(loaderData);
  const setPageBranding = useStore((s) => s.setPageBranding);

  useEffect(() => {
    if (!loaderData) return;
    setPageBranding(loaderData.branding);
    return () => setPageBranding(null);
  }, [loaderData, setPageBranding]);

  const refresh = (id: string) => {
    setTimeout(async () => {
      try {
        const fresh = await getFileShare(id);
        if (fresh) setShare(fresh);
      } catch (e) {
        console.log(e);
      }
    }, REFRESH_AFTER_DOWNLOAD_MS);
  };

  if (!share) {
    return <Centered>{t("file-share-invalid")}</Centered>;
  }

  if (share.status === "expired") {
    return <Centered>{t("file-share-expired")}</Centered>;
  }

  if (share.status === "limit_reached") {
    return <Centered>{t("file-share-limit-reached")}</Centered>;
  }

  const expiresAt = new Date(share.expires_at).toLocaleString(i18n.language, {
    dateStyle: "long",
    timeStyle: "short",
  });

  return (
    <main
      className="flex relative min-h-screen w-full overflow-x-hidden justify-center px-4 py-10"
      style={{ backgroundColor: "var(--bg-color)" }}
    >
      <Stack className="w-full md:max-w-[640px]" gap="md">
        <div>
          <Text fw={600} size="xl">
            {t("file-share-title")}
          </Text>
          {share.organization_name && (
            <Text c="dimmed">
              {t("file-share-from", { name: share.organization_name })}
            </Text>
          )}
          <Text c="dimmed" size="sm">
            {t("file-share-expires", { date: expiresAt })}
          </Text>
          {share.max_downloads !== null && (
            <Text c="dimmed" size="sm">
              {t("file-share-downloads-left", {
                count: share.max_downloads - share.download_count,
              })}
            </Text>
          )}
        </div>

        <Stack gap="xs">
          {share.files.map((file) => (
            <Paper key={file.id} withBorder p="sm" radius="md">
              <Group wrap="nowrap" gap="sm">
                <IconFile size={20} className="shrink-0" />
                <Text className="min-w-0 flex-1 break-words">{file.name}</Text>
                <Button
                  component="a"
                  href={fileShareDownloadURL(share.id, file.id)}
                  variant="light"
                  className="shrink-0"
                  leftSection={<IconDownload size={16} />}
                  onClick={() => refresh(share.id)}
                >
                  {t("download")}
                </Button>
              </Group>
            </Paper>
          ))}
        </Stack>
      </Stack>
    </main>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <main
      className="flex relative min-h-screen w-full overflow-x-hidden items-center justify-center p-6"
      style={{ backgroundColor: "var(--bg-color)" }}
    >
      <Text c="dimmed" ta="center" maw={480}>
        {children}
      </Text>
    </main>
  );
}
