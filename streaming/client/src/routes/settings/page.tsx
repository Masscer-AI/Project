import React, { useEffect, useState, useRef } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { getUser, updateUser } from "../../modules/apiCalls";
import { debounce } from "../../modules/utils";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import i18n from "../../i18next";
import mermaid from "mermaid";
import { TUserProfile } from "../../types/chatTypes";

import {
  ActionIcon,
  Box,
  Button,
  Card,
  Divider,
  FileInput,
  Group,
  Modal,
  NativeSelect,
  PasswordInput,
  SegmentedControl,
  Slider,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import {
  IconDeviceFloppy,
  IconMenu2,
  IconMoon,
  IconDeviceDesktop,
  IconSun,
  IconUpload,
} from "@tabler/icons-react";

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { chatState, toggleSidebar, user, setUser } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
    user: s.user,
    setUser: s.setUser,
  }));
  const { t } = useTranslation();

  useEffect(() => {
    if (!user) {
      getUser().then((data: any) => setUser(data));
    }
  }, []);

  return (
    <main className="d-flex pos-relative h-viewport">
      {chatState.isSidebarOpened && <Sidebar />}
      <div
        style={{
          flex: "1 1 auto",
          minWidth: 0,
          padding: 24,
          overflowY: "auto",
          minHeight: "100vh",
          display: "flex",
          justifyContent: "center",
        }}
        className="relative"
      >
        {!chatState.isSidebarOpened && (
          <Box pos="absolute" top={24} left={24} style={{ zIndex: 10 }}>
            <ActionIcon variant="subtle" color="gray" onClick={toggleSidebar}>
              <IconMenu2 size={20} />
            </ActionIcon>
          </Box>
        )}

        <Box px="md" w="100%" maw="42rem" mx="auto">
          <Title order={2} ta="center" mb="lg" mt="md">
            {t("settings")}
          </Title>

          <Stack gap="lg">
            <UserSection />
            <Divider />
            <PreferencesSection />
            <Divider />
            <ProfileSection />
          </Stack>
        </Box>
      </div>
    </main>
  );
}

// ─── User Section ─────────────────────────────────────────────────────────────

const UserSection = () => {
  const { t } = useTranslation();
  const { user, setUser } = useStore((s) => ({
    user: s.user,
    setUser: s.setUser,
  }));

  const [username, setUsername] = useState(user?.username || "");
  const [email, setEmail] = useState(user?.email || "");
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  useEffect(() => {
    if (user) {
      setUsername(user.username || "");
      setEmail(user.email || "");
    }
  }, [user]);

  const handleSave = async () => {
    try {
      await updateUser({ username, email, profile: user?.profile });
      toast.success(t("user-updated"));
      setUser({ ...user, username, email });
    } catch (e: any) {
      toast.error(t(e.response?.data?.error || "an-error-occurred"));
    }
  };

  const handleChangePassword = async () => {
    if (newPassword.length < 8) {
      toast.error(t("password-min-length"));
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error(t("passwords-do-not-match"));
      return;
    }
    try {
      await updateUser({
        username: user?.username || username,
        email: user?.email || email,
        profile: user?.profile,
        current_password: currentPassword,
        new_password: newPassword,
      });
      toast.success(t("password-updated"));
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordModalOpen(false);
    } catch (e: any) {
      toast.error(t(e.response?.data?.error || "an-error-occurred"));
    }
  };

  const isDirty =
    username !== (user?.username || "") || email !== (user?.email || "");

  const isPasswordReady =
    currentPassword.length > 0 &&
    newPassword.length >= 8 &&
    newPassword === confirmPassword;

  return (
    <Card withBorder p="lg">
      <Title order={4} mb="md">
        {t("user")}
      </Title>
      <Stack gap="sm">
        <TextInput
          label={t("username")}
          value={username}
          onChange={(e) => setUsername(e.currentTarget.value)}
        />
        <TextInput
          label={t("email")}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="subtle" size="xs" onClick={() => setPasswordModalOpen(true)}>
            {t("change-password")}
          </Button>
          <Button
            leftSection={<IconDeviceFloppy size={16} />}
            onClick={handleSave}
            disabled={!isDirty}
          >
            {t("save")}
          </Button>
        </Group>

        <Modal
          opened={passwordModalOpen}
          onClose={() => setPasswordModalOpen(false)}
          title={t("change-password")}
          centered
        >
          <Stack gap="sm">
            <PasswordInput
              label={t("current-password")}
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.currentTarget.value)}
            />
            <PasswordInput
              label={t("new-password")}
              value={newPassword}
              onChange={(e) => setNewPassword(e.currentTarget.value)}
              description={t("password-min-length")}
            />
            <PasswordInput
              label={t("confirm-password")}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.currentTarget.value)}
              error={
                confirmPassword.length > 0 && newPassword !== confirmPassword
                  ? t("passwords-do-not-match")
                  : undefined
              }
            />
            <Group justify="flex-end" mt="sm">
              <Button
                onClick={handleChangePassword}
                disabled={!isPasswordReady}
              >
                {t("change-password")}
              </Button>
            </Group>
          </Stack>
        </Modal>
      </Stack>
    </Card>
  );
};

// ─── Preferences Section (Appearance + Language) ──────────────────────────────

const MERMAID_THEMES = ["dark", "forest", "neutral", "base", "light"];

const PreferencesSection = () => {
  const { t } = useTranslation();
  const { userPreferences, setPreferences, theming, setTheming } = useStore(
    (s) => ({
      userPreferences: s.userPreferences,
      setPreferences: s.setPreferences,
      theming: s.theming,
      setTheming: s.setTheming,
    })
  );

  const debouncedSetOpacity = debounce((opacity: number) => {
    setPreferences({ background_image_opacity: opacity });
  }, 500);

  const currentLang = i18n.language || "en";

  const setLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
    localStorage.setItem("language", lng);
  };

  return (
    <Card withBorder p="lg">
      <Title order={4} mb="md">
        {t("preferences")}
      </Title>

      <Stack gap="md">
        {/* Language */}
        <NativeSelect
          label={t("language")}
          value={currentLang}
          onChange={(e) => setLanguage(e.currentTarget.value)}
          data={[
            { value: "en", label: "English" },
            { value: "es", label: "Español" },
          ]}
        />

        {/* Theme */}
        <div>
          <Text size="sm" fw={500} mb={4}>
            {t("theme")}
          </Text>
          <SegmentedControl
            value={userPreferences.theme || "dark"}
            onChange={(val) =>
              setPreferences({ theme: val as "light" | "dark" | "system" })
            }
            data={[
              {
                value: "light",
                label: (
                  <Group gap={6} wrap="nowrap">
                    <IconSun size={14} /> {t("light")}
                  </Group>
                ),
              },
              {
                value: "dark",
                label: (
                  <Group gap={6} wrap="nowrap">
                    <IconMoon size={14} /> {t("dark")}
                  </Group>
                ),
              },
              {
                value: "system",
                label: (
                  <Group gap={6} wrap="nowrap">
                    <IconDeviceDesktop size={14} /> {t("system")}
                  </Group>
                ),
              },
            ]}
            fullWidth
          />
        </div>

        {/* Background image */}
        <div>
          <Text size="sm" fw={500} mb={4}>
            {t("chat-background-image")}
          </Text>
          <ImageInput
            onResult={(result) =>
              setPreferences({ background_image_source: result })
            }
          />
          <Text size="sm" fw={500} mt="sm" mb={4}>
            {t("opacity-chat-background-image")}
          </Text>
          <Slider
            defaultValue={userPreferences.background_image_opacity ?? 0.5}
            min={0}
            max={1}
            step={0.01}
            onChangeEnd={debouncedSetOpacity}
            label={(v) => `${Math.round(v * 100)}%`}
          />
        </div>

        {/* Mermaid / Diagrams */}
        <div>
          <Text size="sm" fw={500} mb={4}>
            {t("mermaid-theme")}
          </Text>
          <Text size="xs" c="dimmed" mb="xs">
            {t("mermaid-theme-description")}
          </Text>
          <SegmentedControl
            value={theming.mermaid || "dark"}
            onChange={(val) => setTheming({ mermaid: val as any })}
            data={MERMAID_THEMES.map((th) => ({
              value: th,
              label: th.charAt(0).toUpperCase() + th.slice(1),
            }))}
            fullWidth
          />
          <MermaidPreview />
        </div>
      </Stack>
    </Card>
  );
};

const ImageInput = ({ onResult }: { onResult: (b64: string) => void }) => {
  const handleFile = (file: File | null) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Please select a valid image file.");
      return;
    }
    const reader = new FileReader();
    reader.onloadend = () => onResult(reader.result as string);
    reader.readAsDataURL(file);
  };

  const { t } = useTranslation();

  return (
    <FileInput
      placeholder={t("upload-image")}
      accept="image/*"
      onChange={handleFile}
      leftSection={<IconUpload size={16} />}
    />
  );
};

const exampleCode = `graph TD; A-->B; A-->C; B-->D; C-->D;`;
const makeThemeCode = (theme: string) =>
  `%%{init: {'theme':'${theme}'}}%%\n${exampleCode}`;

const MermaidPreview = () => {
  const preRef = useRef<HTMLPreElement>(null);
  const { theming } = useStore((s) => ({ theming: s.theming }));

  useEffect(() => {
    mermaid.initialize({ startOnLoad: true, look: "classic" });
  }, []);

  useEffect(() => {
    if (preRef.current) {
      preRef.current.removeAttribute("data-processed");
      mermaid.run();
    }
  }, [theming.mermaid]);

  return (
    <Box mt="sm" style={{ display: "flex", justifyContent: "center" }}>
      <pre ref={preRef} className="mermaid">
        {makeThemeCode(theming.mermaid)}
      </pre>
    </Box>
  );
};

// ─── Profile Section ──────────────────────────────────────────────────────────

const ProfileSection = () => {
  const { t } = useTranslation();
  const { user, setUser } = useStore((s) => ({
    user: s.user,
    setUser: s.setUser,
  }));

  const [profile, setProfile] = useState<Partial<TUserProfile>>(
    user?.profile || {}
  );
  const [saving, setSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    if (user?.profile) {
      setProfile(user.profile);
      setIsDirty(false);
    }
  }, [user]);

  const updateField = (key: string, value: any) => {
    setProfile((prev) => ({ ...prev, [key]: value }));
    setIsDirty(true);
  };

  const handleSave = async () => {
    if (!user) return;
    setSaving(true);
    try {
      await updateUser({
        username: user.username,
        email: user.email,
        profile: profile as TUserProfile,
      });
      toast.success(t("user-updated"));
      setUser({ ...user, profile: profile as TUserProfile });
      setIsDirty(false);
    } catch (e: any) {
      toast.error(t(e.response?.data?.error || "an-error-occurred"));
    } finally {
      setSaving(false);
    }
  };

  const handleAvatarChange = (file: File | null) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onloadend = () => updateField("avatar_url", reader.result as string);
    reader.readAsDataURL(file);
  };

  return (
    <Card withBorder p="lg">
      <Title order={4} mb={4}>
        {t("profile")}
      </Title>
      <Text size="sm" c="dimmed" mb="md">
        {t("profile-helptext")}
      </Text>

      <Stack gap="sm">
        <TextInput
          label={t("name")}
          value={profile.name || ""}
          onChange={(e) => updateField("name", e.currentTarget.value)}
        />
        <DatePickerInput
          label={t("birthday")}
          value={profile.birthday ? new Date(profile.birthday) : null}
          onChange={(val: any) => {
            if (!val) {
              updateField("birthday", "");
              return;
            }
            const d = val instanceof Date ? val : new Date(val);
            updateField("birthday", d.toISOString().split("T")[0]);
          }}
          clearable
        />
        <TextInput
          label={t("sex")}
          value={profile.sex || ""}
          onChange={(e) => updateField("sex", e.currentTarget.value)}
        />
        <Textarea
          label={t("bio")}
          value={profile.bio || ""}
          onChange={(e) => updateField("bio", e.currentTarget.value)}
          minRows={3}
          autosize
        />
        <div>
          <Text size="sm" fw={500} mb={4}>
            {t("avatar")}
          </Text>
          <Group gap="sm" align="center">
            {profile.avatar_url && (
              <img
                src={profile.avatar_url}
                alt="avatar"
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: "50%",
                  objectFit: "cover",
                }}
              />
            )}
            <FileInput
              placeholder={t("upload-image")}
              accept="image/*"
              onChange={handleAvatarChange}
              leftSection={<IconUpload size={16} />}
              style={{ flex: 1 }}
            />
          </Group>
        </div>

        <Group justify="flex-end" mt="xs">
          <Button
            leftSection={<IconDeviceFloppy size={16} />}
            onClick={handleSave}
            loading={saving}
            disabled={!isDirty}
          >
            {t("save-profile")}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
};
