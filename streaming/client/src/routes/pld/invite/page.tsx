import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { Loader, Stack, Text, Title } from "@mantine/core";
import { acceptPldInvite } from "../../../modules/apiCalls";
import { loginUrlWithNext } from "../../../utils/loginRedirect";

export default function PldInviteAcceptPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [message, setMessage] = useState(t("loading"));

  useEffect(() => {
    if (!token) {
      navigate("/login", { replace: true });
      return;
    }
    if (!localStorage.getItem("token")) {
      navigate(loginUrlWithNext(`/pld/invite?token=${token}`), { replace: true });
      return;
    }
    let cancelled = false;
    acceptPldInvite(token)
      .then(() => {
        if (cancelled) return;
        toast.success(t("compliance-invite-accepted"));
        navigate("/pld/expediente", { replace: true });
      })
      .catch(() => {
        if (cancelled) return;
        setMessage(t("invite-invalid-or-expired"));
      });
    return () => {
      cancelled = true;
    };
  }, [token, navigate, t]);

  return (
    <Stack align="center" justify="center" h="100vh" gap="md">
      <Loader color="violet" />
      <Title order={3}>{t("compliance-hub-title")}</Title>
      <Text c="dimmed" size="sm">
        {message}
      </Text>
    </Stack>
  );
}
