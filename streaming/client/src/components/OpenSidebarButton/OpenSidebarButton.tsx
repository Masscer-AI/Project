import { ActionIcon, Badge, Box } from "@mantine/core";
import { IconMenu2 } from "@tabler/icons-react";
import { useTranslation } from "react-i18next";
import {
  formatUnreadNotificationBadge,
  useUnreadNotificationCount,
} from "../../hooks/useUnreadNotificationCount";
import { useStore } from "../../modules/store";

export function OpenSidebarButton() {
  const { t } = useTranslation();
  const opened = useStore((s) => s.chatState.isSidebarOpened);
  const toggleSidebar = useStore((s) => s.toggleSidebar);
  const unreadNotificationCount = useUnreadNotificationCount();

  if (opened) return null;

  return (
    <Box
      pos="relative"
      style={{ display: "inline-block", alignSelf: "flex-start", marginBottom: 8 }}
    >
      <ActionIcon
        variant="subtle"
        color="gray"
        onClick={toggleSidebar}
        aria-label={t("open-sidebar")}
      >
        <IconMenu2 size={20} />
      </ActionIcon>
      {unreadNotificationCount > 0 && (
        <Badge
          color="red"
          size="sm"
          radius="xl"
          variant="filled"
          pos="absolute"
          top={-4}
          right={-4}
          styles={{ root: { pointerEvents: "none", minWidth: 20 } }}
        >
          {formatUnreadNotificationBadge(unreadNotificationCount)}
        </Badge>
      )}
    </Box>
  );
}
