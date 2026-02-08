import React, { useState } from "react";
import axios from "axios";
import { toast } from "react-hot-toast";
import { useNavigate, Link } from "react-router-dom";
import { API_URL } from "../../modules/constants";
import { useTranslation } from "react-i18next";

import {
  TextInput,
  PasswordInput,
  Button,
  Title,
  Text,
  Stack,
  Anchor,
} from "@mantine/core";
import { IconLogin, IconSparkles } from "@tabler/icons-react";

const panelBase = "flex-1 flex flex-col justify-center items-center p-8";
const panelLeft =
  "bg-[radial-gradient(ellipse_80%_60%_at_30%_50%,rgba(110,91,255,0.15),transparent),linear-gradient(180deg,rgba(20,20,25,0.98)_0%,rgba(15,15,20,0.99)_100%)] border-r border-white/[0.06] md:min-h-0 min-h-[40vh] md:border-b-0 border-b border-white/[0.06]";
const panelRight = "bg-[var(--bg-color,#0a0a0a)] md:min-h-0 min-h-[60vh]";
const formCard =
  "w-full max-w-[400px] p-10 rounded-2xl border border-white/[0.08] shadow-2xl bg-[var(--modal-bg-color,rgba(28,28,32,0.98))]";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleSubmit = async () => {
    if (!email || !password) {
      toast.error(t("email-and-password-required"));
      return;
    }

    setIsLoading(true);
    setErrorMessage("");
    try {
      const response = await axios.post(API_URL + "/v1/auth/login", {
        email,
        password,
      });
      if (response.data.token) {
        localStorage.setItem("token", response.data.token);
      }
      toast.success(t("successfully-logged-in"));
      navigate("/chat");
    } catch (error: any) {
      console.error("LOGIN ERROR: ", error);
      const msg =
        error.code === "ERR_NETWORK"
          ? t("network-error")
          : error.response?.data?.detail || t("an-error-occurred");
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSubmit();
    }
  };

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-[var(--bg-color,#0a0a0a)] text-[var(--font-color,#fff)]">
      {/* Left panel — branding */}
      <div className={`${panelBase} ${panelLeft}`}>
        <div className="text-center max-w-[380px]">
          <div className="w-[88px] h-[88px] mx-auto mb-6 rounded-2xl flex items-center justify-center bg-[rgba(110,91,255,0.2)] border border-[rgba(110,91,255,0.3)]">
            <IconSparkles size={40} className="text-white/90" />
          </div>
          <Title order={1} className="!text-[1.75rem] !font-semibold !mb-3">
            {t("welcome-back")}
          </Title>
          <Text size="sm" c="dimmed" className="leading-relaxed">
            {t("login-description")}
          </Text>
        </div>
      </div>

      {/* Right panel — form */}
      <div className={`${panelBase} ${panelRight}`}>
        <div className={formCard}>
          <Title order={2} ta="center" mb="xl">
            {t("login")}
          </Title>

          <form onSubmit={(e) => e.preventDefault()}>
            <Stack gap="md">
              <TextInput
                label={t("email")}
                placeholder={t("email")}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.currentTarget.value)}
                onKeyDown={handleKeyDown}
                required
                name="email"
                autoComplete="email"
                variant="filled"
                size="md"
              />
              <PasswordInput
                label={t("password")}
                placeholder={t("password")}
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
                onKeyDown={handleKeyDown}
                required
                name="password"
                autoComplete="current-password"
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
                leftSection={!isLoading ? <IconLogin size={18} /> : undefined}
              >
                {t("login")}
              </Button>
            </Stack>
          </form>

          <Text ta="center" mt="xl" size="sm">
            <Anchor component={Link} to="/signup" c="violet">
              {t("go-to-signup")}
            </Anchor>
          </Text>
        </div>
      </div>
    </div>
  );
}
