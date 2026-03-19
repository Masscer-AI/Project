import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "react-hot-toast";
import {
  TextInput,
  Button,
  Title,
  Text,
  Stack,
  Anchor,
} from "@mantine/core";
import { IconMail, IconSparkles } from "@tabler/icons-react";

import { requestPasswordReset } from "../../modules/apiCalls";

const panelBase = "flex-1 flex flex-col justify-center items-center p-8";
const panelLeft =
  "bg-[radial-gradient(ellipse_80%_60%_at_30%_50%,rgba(110,91,255,0.15),transparent),linear-gradient(180deg,rgba(20,20,25,0.98)_0%,rgba(15,15,20,0.99)_100%)] border-r border-white/[0.06] md:min-h-0 min-h-[40vh] md:border-b-0 border-b border-white/[0.06]";
const panelRight = "bg-[var(--bg-color,#0a0a0a)] md:min-h-0 min-h-[60vh]";
const formCard =
  "w-full max-w-[420px] p-10 rounded-2xl border border-white/[0.08] shadow-2xl bg-[var(--modal-bg-color,rgba(28,28,32,0.98))]";

export default function ForgotPassword() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async () => {
    if (!email) {
      toast.error(t("email-required"));
      return;
    }

    setIsLoading(true);
    try {
      await requestPasswordReset(email);
      setSubmitted(true);
      toast.success(t("reset-link-sent"));
    } catch {
      toast.error(t("an-error-occurred"));
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
            {t("forgot-your-password")}
          </Title>
          <Text size="sm" c="dimmed" className="leading-relaxed">
            {t("forgot-password-description")}
          </Text>
        </div>
      </div>

      <div className={`${panelBase} ${panelRight}`}>
        <div className={formCard}>
          <Title order={2} ta="center" mb="xl">
            {t("forgot-password")}
          </Title>

          {!submitted ? (
            <Stack gap="md">
              <TextInput
                label={t("email")}
                placeholder={t("email")}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.currentTarget.value)}
                required
                autoComplete="email"
                variant="filled"
                size="md"
              />
              <Button
                onClick={handleSubmit}
                loading={isLoading}
                fullWidth
                size="md"
                mt="xs"
                leftSection={!isLoading ? <IconMail size={18} /> : undefined}
              >
                {t("send-reset-link")}
              </Button>
            </Stack>
          ) : (
            <Stack gap="xs">
              <Text ta="center" c="dimmed">
                {t("reset-link-sent-description")}
              </Text>
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
