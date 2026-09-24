import React from "react";
import { Box, Stack, Text } from "@mantine/core";
import { IconPhoto } from "@tabler/icons-react";
import type { WhatsappTemplate } from "./shared";

export function fillTemplatePlaceholders(
  text: string,
  values?: string[]
): string {
  if (!values?.length) return text || "";
  return (text || "").replace(/\{\{(\d+)\}\}/g, (match, n) => {
    const idx = Number(n) - 1;
    const value = idx >= 0 && idx < values.length ? (values[idx] || "").trim() : "";
    return value || match;
  });
}

export function waInline(text: string): React.ReactNode[] {
  return text
    .split(/(\*[^*\n]+\*|_[^_\n]+_|~[^~\n]+~|\{\{\d+\}\})/g)
    .map((part, index) => {
      if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
        return (
          <Text key={index} span fw={700}>
            {part.slice(1, -1)}
          </Text>
        );
      }
      if (part.startsWith("_") && part.endsWith("_") && part.length > 2) {
        return (
          <Text key={index} span fs="italic">
            {part.slice(1, -1)}
          </Text>
        );
      }
      if (part.startsWith("~") && part.endsWith("~") && part.length > 2) {
        return (
          <Text key={index} span td="line-through">
            {part.slice(1, -1)}
          </Text>
        );
      }
      if (/^\{\{\d+\}\}$/.test(part)) {
        return (
          <Text
            key={index}
            span
            fw={600}
            style={{
              background: "rgba(255,255,255,0.14)",
              borderRadius: 4,
              padding: "0 3px",
            }}
          >
            {part}
          </Text>
        );
      }
      return <React.Fragment key={index}>{part}</React.Fragment>;
    });
}

export function WhatsappTemplatePreview({
  template,
  bodyValues,
  headerValues,
}: {
  template: WhatsappTemplate;
  bodyValues?: string[];
  headerValues?: string[];
}) {
  const header = fillTemplatePlaceholders(
    template.header_text || "",
    headerValues
  ).trim();
  const body = fillTemplatePlaceholders(template.body_text || "", bodyValues).trim();
  const footer = (template.footer_text || "").trim();
  const buttons = template.buttons || [];
  const showImage =
    template.requires_header_image ||
    (template.header_type || "").toUpperCase() === "IMAGE";

  return (
    <Box p="md" style={{ background: "#0b141a", borderRadius: 12 }}>
      <Box
        maw={340}
        ml="auto"
        style={{
          background: "#005c4b",
          color: "#e9edef",
          borderRadius: "8px 8px 0 8px",
          overflow: "hidden",
        }}
      >
        {showImage ? (
          <Box
            h={120}
            style={{
              background: "#1f2c34",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <IconPhoto size={28} color="#8696a0" />
          </Box>
        ) : null}
        <Stack gap={6} p="sm">
          {header ? (
            <Text size="sm" fw={700}>
              {waInline(header)}
            </Text>
          ) : null}
          {body ? (
            <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
              {waInline(body)}
            </Text>
          ) : null}
          {footer ? (
            <Text size="xs" c="rgba(233,237,239,0.65)">
              {footer}
            </Text>
          ) : null}
        </Stack>
        {buttons.map((button, index) => {
          const label = (button.label || "").trim() || `Button ${index + 1}`;
          return (
            <Box
              key={`${template.template_id}-btn-${index}`}
              style={{
                borderTop: "1px solid rgba(255,255,255,0.12)",
                padding: "8px 12px",
                textAlign: "center",
                color: "#53bdeb",
                fontWeight: 600,
                fontSize: 13,
              }}
            >
              {label}
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
