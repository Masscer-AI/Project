import React, { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "react-hot-toast";
import {
  PasswordInput,
  Button,
  Title,
  Text,
  Stack,
  Anchor,
} from "@mantine/core";
import { IconKey, IconSparkles } from "@tabler/icons-react";

import { confirmPasswordReset } from "../../modules/apiCalls";

const panelBase = "flex-1 flex flex-col justify-center items-center p-8";
const panelLeft =
  "bg-[radial-gradient(ellipse_80%_60%_at_30%_50%,rgba(110,91,255,0.15),transparent),linear-gradient(180deg,rgba(20,20,25,0.98)_0%,rgba(15,15,20,0.99)_100%)] border-r border-white/[0.06] md:min-h-0 min-h-[40vh] md:border-b-0 border-b border-white/[0.06]";
const panelRight = "bg-[var(--bg-color,#0a0a0a)] md:min-h-0 min-h-[60vh]";
const formCard =
  "w-full max-w-[420px] p-10 rounded-2xl border border-white/[0.08] shadow-2xl bg-[var(--modal-bg-color,rgba(28,28,32,0.98))]";

export default function ResetPassword() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const uid = searchParams.get("uid") || "";
  const token = searchParams.get("token") || "";
  const hasValidParams = useMemo(() => Boolean(uid && token), [uid, token]);

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async () => {
    if (newPassword.length < 8) {
      toast.error(t("password-min-length"));
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error(t("passwords-do-not-match"));
      return;
    }

    setIsLoading(true);
    setErrorMessage("");
    try {
      await confirmPasswordReset({
        uid,
        token,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      toast.success(t("reset-password-success"));
      navigate("/login");
    } catch (error: any) {
      const serverError = error?.response?.data?.error;
      if (serverError === "invalid-or-expired-reset-link") {
        setErrorMessage(t("invalid-or-expired-reset-link"));
      } else {
        setErrorMessage(t("an-error-occurred"));
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
      <div className={`${panelBase} ${panelLeft}`}>
        <div className="text-center max-w-[380px]">
          <div className="w-[88px] h-[88px] mx-auto mb-6 rounded-2xl flex items-center justify-center bg-[rgba(110,91,255,0.2)] border border-[rgba(110,91,255,0.3)]">
            <IconSparkles size={40} className="text-white/90" />
          </div>
          <Title order={1} className="!text-[1.75rem] !font-semibold !mb-3">
            {t("reset-password")}
          </Title>
          <Text size="sm" c="dimmed" className="leading-relaxed">
            {t("reset-password-description")}
          </Text>
        </div>
      </div>

      <div className={`${panelBase} ${panelRight}`}>
        <div className={formCard}>
          <Title order={2} ta="center" mb="xl">
            {t("reset-password")}
          </Title>

          {!hasValidParams ? (
            <Stack gap="md">
              <Text ta="center" c="red">
                {t("invalid-or-expired-reset-link")}
              </Text>
              <Anchor component={Link} to="/forgot-password" ta="center" c="violet">
                {t("request-new-reset-link")}
              </Anchor>
            </Stack>
          ) : (
            <Stack gap="md">
              <PasswordInput
                label={t("new-password")}
                placeholder={t("new-password")}
                value={newPassword}
                onChange={(e) => setNewPassword(e.currentTarget.value)}
                autoComplete="new-password"
                required
                variant="filled"
                size="md"
              />
              <PasswordInput
                label={t("confirm-password")}
                placeholder={t("confirm-password")}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.currentTarget.value)}
                autoComplete="new-password"
                required
                variant="filled"
                size="md"
              />

              {errorMessage && (
                <Text size="sm" c="red" ta="center">
                  {errorMessage}
                </Text>
              )}

              <Button
                onClick={handleSubmit}
                loading={isLoading}
                fullWidth
                size="md"
                mt="xs"
                leftSection={!isLoading ? <IconKey size={18} /> : undefined}
              >
                {t("reset-password")}
              </Button>
            </Stack>
          )}

          <Text ta="center" mt="xl" size="sm">
            <Anchor component={Link} to="/login" c="violet">
              {t("back-to-login")}
            </Anchor>
          </Text>
        </div>
      </div>
    </div>
  );
}
