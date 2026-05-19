import React from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";
import { Alert, Anchor, Group, Text } from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import {
  OrganizationSubscriptionWarningKind,
  useOrganizationSubscriptionWarning,
} from "../../hooks/useOrganizationSubscriptionWarning";

const MESSAGE_KEY: Record<
  Exclude<OrganizationSubscriptionWarningKind, "none">,
  string
> = {
  no_subscription: "org-subscription-banner-no-subscription",
  inactive: "org-subscription-banner-inactive",
  inactive_with_purchased: "org-subscription-banner-inactive-with-purchased",
};

/**
 * Sticky warning for org managers when the organization subscription is missing or inactive.
 */
export const OrganizationSubscriptionBanner: React.FC = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const { showBanner, kind, billingHref } = useOrganizationSubscriptionWarning();

  if (!showBanner || kind === "none") return null;

  const onBillingTab =
    location.pathname === "/organization" &&
    (new URLSearchParams(location.search).get("activeTab") ?? "") ===
      "billing";

  if (onBillingTab) return null;

  return (
    <Alert
      color="red"
      variant="filled"
      icon={<IconAlertTriangle size={18} />}
      radius={0}
      style={{
        position: "sticky",
        top: 0,
        zIndex: 200,
      }}
      styles={{
        root: {
          borderBottom: "1px solid rgba(0,0,0,0.2)",
        },
      }}
    >
      <Group justify="space-between" wrap="wrap" gap="xs" align="center">
        <Text size="sm" fw={500} style={{ flex: 1, minWidth: 200 }}>
          {t(MESSAGE_KEY[kind])}
        </Text>
        <Anchor
          component={Link}
          to={billingHref}
          size="sm"
          fw={600}
          c="white"
          underline="always"
        >
          {t("org-subscription-banner-go-to-billing")}
        </Anchor>
      </Group>
    </Alert>
  );
};
