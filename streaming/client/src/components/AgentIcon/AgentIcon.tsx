import type { CSSProperties } from "react";
import {
  IconBook,
  IconBooks,
  IconBriefcase,
  IconBulb,
  IconBuilding,
  IconBuildingBank,
  IconCalculator,
  IconChartBar,
  IconCode,
  IconDatabase,
  IconFileText,
  IconGavel,
  IconHeadset,
  IconLeaf,
  IconLock,
  IconMail,
  IconMessage,
  IconPhone,
  IconRobot,
  IconScale,
  IconSchool,
  IconSearch,
  IconShield,
  IconShieldCheck,
  IconSparkles,
  IconStar,
  IconStethoscope,
  IconUser,
  IconUsers,
  IconWorld,
} from "@tabler/icons-react";

const AGENT_ICONS = {
  robot: IconRobot,
  sparkles: IconSparkles,
  user: IconUser,
  users: IconUsers,
  message: IconMessage,
  headset: IconHeadset,
  briefcase: IconBriefcase,
  building: IconBuilding,
  "building-bank": IconBuildingBank,
  scale: IconScale,
  gavel: IconGavel,
  shield: IconShield,
  "shield-check": IconShieldCheck,
  lock: IconLock,
  book: IconBook,
  books: IconBooks,
  school: IconSchool,
  "file-text": IconFileText,
  search: IconSearch,
  bulb: IconBulb,
  "chart-bar": IconChartBar,
  calculator: IconCalculator,
  database: IconDatabase,
  code: IconCode,
  stethoscope: IconStethoscope,
  leaf: IconLeaf,
  world: IconWorld,
  mail: IconMail,
  phone: IconPhone,
  star: IconStar,
} as const;

export const AGENT_ICON_NAMES = Object.keys(AGENT_ICONS);

export const DEFAULT_AGENT_ICON = "robot";

export function AgentIcon({
  name,
  size = 16,
  style,
}: {
  name?: string;
  size?: number;
  style?: CSSProperties;
}) {
  const Icon = AGENT_ICONS[(name || DEFAULT_AGENT_ICON) as keyof typeof AGENT_ICONS] || IconRobot;
  return <Icon size={size} style={style} />;
}
