import { ActionIcon, Badge, Box } from "@mantine/core";
import { IconMenu2, IconX } from "@tabler/icons-react";
import { useTranslation } from "react-i18next";
import {
  formatUnreadNotificationBadge,
  useUnreadNotificationCount,
} from "../../hooks/useUnreadNotificationCount";
import { useStore } from "../../modules/store";

export function OpenSidebarButton({ flush = false }: { flush?: boolean }) {
  const { t } = useTranslation();
  const opened = useStore((s) => s.chatState.isSidebarOpened);
  const toggleSidebar = useStore((s) => s.toggleSidebar);
  const unreadNotificationCount = useUnreadNotificationCount();
  const label = opened ? t("close-sidebar") : t("open-sidebar");

  return (
    <Box
      style={{
        display: "inline-block",
        alignSelf: "flex-start",
        marginBottom: flush ? 0 : 8,
        position: "relative",
      }}
    >
      <ActionIcon
        variant="subtle"
        color="gray"
        onClick={toggleSidebar}
        aria-label={label}
      >
        {opened ? <IconX size={20} /> : <IconMenu2 size={20} />}
      </ActionIcon>
      {!opened && unreadNotificationCount > 0 && (
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
