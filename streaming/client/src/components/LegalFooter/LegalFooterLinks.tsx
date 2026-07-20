import React from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Anchor, Group, type GroupProps, Text } from "@mantine/core";

type Props = GroupProps;

export function LegalFooterLinks(props: Props) {
  const { t } = useTranslation();
  const location = useLocation();
  const onPrivacy = location.pathname === "/privacy";
  const onTerms = location.pathname === "/terms";

  return (
    <Group gap="xs" justify="center" wrap="wrap" {...props}>
      {!onPrivacy && (
        <Anchor component={Link} to="/privacy" size="xs" c="dimmed">
          {t("legal-privacy-link")}
        </Anchor>
      )}
      {!onPrivacy && !onTerms && (
        <Text size="xs" c="dimmed" aria-hidden>
          ·
        </Text>
      )}
      {!onTerms && (
        <Anchor component={Link} to="/terms" size="xs" c="dimmed">
          {t("legal-terms-link")}
        </Anchor>
      )}
    </Group>
  );
}
