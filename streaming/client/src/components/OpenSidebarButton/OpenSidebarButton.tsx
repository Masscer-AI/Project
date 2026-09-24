import { ActionIcon, Badge, Box } from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
import {
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
  IconMenu2,
  IconX,
} from "@tabler/icons-react";
import { useTranslation } from "react-i18next";
import {
  formatUnreadNotificationBadge,
  useUnreadNotificationCount,
} from "../../hooks/useUnreadNotificationCount";
import { useStore } from "../../modules/store";

export function OpenSidebarButton({ flush = false }: { flush?: boolean }) {
  const { t } = useTranslation();
  const isDesktop = useMediaQuery("(min-width: 48em)");
  const opened = useStore((s) => s.chatState.isSidebarOpened);
  const collapsed = useStore((s) => s.chatState.sidebarCollapsed);
  const toggleSidebar = useStore((s) => s.toggleSidebar);
  const toggleSidebarCollapsed = useStore((s) => s.toggleSidebarCollapsed);
  const unreadNotificationCount = useUnreadNotificationCount();
  const label = isDesktop
    ? collapsed
      ? t("expand-sidebar")
      : t("collapse-sidebar")
    : opened
      ? t("close-sidebar")
      : t("open-sidebar");
  const icon = isDesktop ? (
    collapsed ? (
      <IconLayoutSidebarLeftExpand size={20} />
    ) : (
      <IconLayoutSidebarLeftCollapse size={20} />
    )
  ) : opened ? (
    <IconX size={20} />
  ) : (
    <IconMenu2 size={20} />
  );
  const showBadge =
    unreadNotificationCount > 0 &&
    (isDesktop ? collapsed : !opened);

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
        onClick={isDesktop ? toggleSidebarCollapsed : toggleSidebar}
        aria-label={label}
      >
        {icon}
      </ActionIcon>
      {showBadge && (
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
