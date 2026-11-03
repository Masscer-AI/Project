import React from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Group, Modal, Text, Tooltip } from "@mantine/core";
import { IconDownload, IconMaximize } from "@tabler/icons-react";
import { HtmlFrame } from "./HtmlFrame";

function openHtml(src: string) {
  window.open(src, "_blank", "noopener,noreferrer");
}

function downloadHtml(src: string, name: string) {
  const a = document.createElement("a");
  a.href = src;
  a.setAttribute("download", name || "file.html");
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export function HtmlPreviewModal({
  opened,
  onClose,
  src,
  title,
}: {
  opened: boolean;
  onClose: () => void;
  src: string;
  title: string;
}) {
  const { t } = useTranslation();
  const label = title || t("html-preview");

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group justify="space-between" wrap="nowrap" style={{ width: "100%" }}>
          <Text fw={600} size="lg" lineClamp={1} style={{ minWidth: 0 }}>
            {label}
          </Text>
          <Tooltip label={t("download")} withArrow>
            <ActionIcon
              variant="subtle"
              color="gray"
              size="md"
              onClick={() => downloadHtml(src, title)}
              aria-label={t("download")}
            >
              <IconDownload size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
      }
      size="95vw"
      centered
      padding="md"
      styles={{
        header: { paddingBottom: 12 },
        body: { paddingTop: 8 },
      }}
    >
      {opened ? <HtmlFrame src={src} title={label} height="75vh" /> : null}
    </Modal>
  );
}

export function HtmlInlinePreview({ src, title }: { src: string; title: string }) {
  const { t } = useTranslation();
  const label = title || t("html-preview");

  return (
    <span className="html-preview">
      <span className="html-preview-bar">
        <span className="html-preview-title">{label}</span>
        <span className="html-preview-actions">
          <Tooltip label={t("expand")} withArrow>
            <ActionIcon
              variant="subtle"
              color="gray"
              size="sm"
              onClick={() => openHtml(src)}
              aria-label={t("expand")}
            >
              <IconMaximize size={16} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label={t("download")} withArrow>
            <ActionIcon
              variant="subtle"
              color="gray"
              size="sm"
              onClick={() => downloadHtml(src, title)}
              aria-label={t("download")}
            >
              <IconDownload size={16} />
            </ActionIcon>
          </Tooltip>
        </span>
      </span>
      <HtmlFrame src={src} title={label} height={420} />
    </span>
  );
}
