import React, { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Anchor,
  Container,
  Group,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { LegalMarkdown } from "../../components/LegalMarkdown/LegalMarkdown";
import "../../components/LegalMarkdown/LegalMarkdown.css";
import {
  getLegalMarkdown,
  LEGAL_LAST_UPDATED,
  LegalDocId,
} from "./legalDocuments";
import { LegalFooterLinks } from "../../components/LegalFooter/LegalFooterLinks";

const TITLE_KEYS: Record<LegalDocId, string> = {
  privacy: "legal-privacy-title",
  terms: "legal-terms-title",
};

type Props = {
  docId: LegalDocId;
};

export function LegalDocumentPage({ docId }: Props) {
  const { t, i18n } = useTranslation();
  const markdown = useMemo(
    () => getLegalMarkdown(docId, i18n.language),
    [docId, i18n.language]
  );

  return (
    <div className="min-h-screen bg-[var(--bg-color,#0a0a0a)] py-10 px-4">
      <Container size="sm">
        <Stack gap="lg">
          <Group justify="space-between" align="flex-start" wrap="wrap">
            <Stack gap={4}>
              <Title order={1} size="h2">
                {t(TITLE_KEYS[docId])}
              </Title>
              <Text size="xs" c="dimmed">
                {t("legal-last-updated", { date: LEGAL_LAST_UPDATED })}
              </Text>
            </Stack>
            <Anchor component={Link} to="/login" size="sm">
              {t("legal-back-to-app")}
            </Anchor>
          </Group>

          <LegalMarkdown markdown={markdown} />

          <LegalFooterLinks justify="flex-start" mt="md" />
        </Stack>
      </Container>
    </div>
  );
}
