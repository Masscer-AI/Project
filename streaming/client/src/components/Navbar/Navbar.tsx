import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Box, Button, Group } from "@mantine/core";
import { API_URL, DEFAULT_ORGANIZATION_ID } from "../../modules/constants";
import { useStore } from "../../modules/store";

/** Logo: replace `streaming/client/public/assets/masscer.png` with your image,
 *  or change the `src` below to another path (e.g. `assets/your-logo.png`). */
const DEFAULT_LOGO_SRC = "assets/masscer.png";

export const Navbar = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantBranding = useStore((s) => s.tenantBranding);

  const logoSrc = tenantBranding?.logo_url
    ? `${API_URL}${tenantBranding.logo_url}`
    : DEFAULT_LOGO_SRC;
  const appName = tenantBranding?.app_name || "Masscer";

  const handleSignupClick = () => {
    const signupUrl = DEFAULT_ORGANIZATION_ID
      ? `/signup?orgId=${DEFAULT_ORGANIZATION_ID}`
      : "/signup";
    navigate(signupUrl);
  };

  return (
    <Box
      component="nav"
      py="md"
      px={{ base: "md", xs: "xl" }}
      style={{
        borderBottom: "1px solid var(--mantine-color-dark-4)",
      }}
    >
      <Group justify="space-between" w="100%" wrap="nowrap">
        <Link to="/" aria-label={`${appName} home`} style={{ display: "flex", alignItems: "center" }}>
          <img
            src={logoSrc}
            alt={appName}
            style={{
              height: 36,
              width: "auto",
              display: "block",
              objectFit: "contain",
            }}
          />
        </Link>
        <Group gap="sm">
          <Button variant="filled" onClick={handleSignupClick}>
            {t("signup")}
          </Button>
          <Button component={Link} to="/login" variant="default">
            {t("login")}
          </Button>
        </Group>
      </Group>
    </Box>
  );
};
