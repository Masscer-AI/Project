import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  motion,
  AnimatePresence,
  useScroll,
  useTransform,
  useSpring,
  useMotionValueEvent,
} from "framer-motion";
import {
  Box,
  Button,
  Card,
  Flex,
  Group,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
import {
  IconBrandWhatsapp,
  IconPhoto,
  IconRobot,
  IconSparkles,
  IconUsers,
  IconWorldWww,
} from "@tabler/icons-react";
import { DEFAULT_ORGANIZATION_ID } from "../../modules/constants";

const FEATURES = [
  {
    icon: IconRobot,
    titleKey: "landing-create-agents-title",
    descKey: "landing-create-agents-description",
  },
  {
    icon: IconUsers,
    titleKey: "landing-manage-relationships-title",
    descKey: "landing-manage-relationships-description",
  },
  {
    icon: IconWorldWww,
    titleKey: "landing-embed-website-title",
    descKey: "landing-embed-website-description",
  },
  {
    icon: IconBrandWhatsapp,
    titleKey: "landing-automate-whatsapp-title",
    descKey: "landing-automate-whatsapp-description",
  },
];

type MockupSection = "chat" | "alerts" | "embed" | "whatsapp" | "media";

const getMockupSection = (progress: number): MockupSection => {
  if (progress < 0.2) return "chat";
  if (progress < 0.4) return "alerts";
  if (progress < 0.6) return "embed";
  if (progress < 0.8) return "whatsapp";
  return "media";
};

const bubbleStyle = (align: "start" | "end") => ({
  alignSelf: align === "start" ? ("flex-start" as const) : ("flex-end" as const),
  background: "rgba(139, 92, 246, 0.2)",
  borderRadius: 12,
  borderBottomLeftRadius: align === "start" ? 4 : 12,
  borderBottomRightRadius: align === "end" ? 4 : 12,
  maxWidth: "80%",
  p: "xs" as const,
});

const MockupContent = ({
  activeSection,
  compact,
}: {
  activeSection: MockupSection;
  compact: boolean;
}) => {
  const { t } = useTranslation();
  const stackGap = compact ? "xs" : "md";
  const stackP = compact ? "sm" : "md";
  const headerP = compact ? "xs" : "sm";
  const inputP = compact ? "xs" : "sm";

  if (activeSection === "alerts") {
    return (
      <>
        <Box
          p={headerP}
          style={{
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            background: "rgba(0,0,0,0.2)",
          }}
        >
          <Group gap="xs">
            <Box w={8} h={8} style={{ borderRadius: 4, background: "#f59e0b" }} />
            <Text size="xs" c="dimmed" fw={600}>
              {t("landing-mockup-alerts-title")}
            </Text>
          </Group>
        </Box>
        <Stack gap={stackGap} p={stackP} style={{ flex: 1 }}>
          {[
            "landing-mockup-alert-1",
            "landing-mockup-alert-2",
            "landing-mockup-alert-3",
            compact ? null : "landing-mockup-alert-4",
          ]
            .filter(Boolean)
            .map((key) => (
              <Box
                key={key!}
                p="xs"
                style={{
                  background: "rgba(245, 158, 11, 0.15)",
                  border: "1px solid rgba(245, 158, 11, 0.25)",
                  borderRadius: 12,
                  borderLeft: "3px solid #f59e0b",
                }}
              >
                <Text size="xs" c="gray.3">
                  {t(key!)}
                </Text>
              </Box>
            ))}
        </Stack>
      </>
    );
  }

  if (activeSection === "embed") {
    return (
      <>
        <Box
          p={headerP}
          style={{
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            background: "rgba(0,0,0,0.2)",
          }}
        >
          <Group gap="xs">
            <Box
              w={8}
              h={8}
              style={{ borderRadius: 4, background: "#22c55e" }}
            />
            <Text size="xs" c="dimmed" fw={600}>
              {t("landing-mockup-embed-title")}
            </Text>
          </Group>
        </Box>
        {/* Blurred website background + floating chat widget */}
        <Box
          p={stackP}
          style={{
            flex: 1,
            position: "relative",
            overflow: "hidden",
          }}
        >
          <Box
            style={{
              position: "absolute",
              inset: 0,
              background:
                "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.02) 2px, rgba(255,255,255,0.02) 4px)",
              filter: "blur(8px)",
              opacity: 0.8,
            }}
          />
          <Box
            style={{
              position: "absolute",
              bottom: compact ? 8 : 16,
              right: compact ? 8 : 16,
              width: compact ? 140 : 180,
              background: "rgba(34, 197, 94, 0.95)",
              backdropFilter: "blur(12px)",
              borderRadius: 16,
              border: "1px solid rgba(34, 197, 94, 0.4)",
              boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
              overflow: "hidden",
            }}
          >
            <Box p="xs" style={{ borderBottom: "1px solid rgba(0,0,0,0.1)" }}>
              <Text size="xs" c="dark.7" fw={600}>
                {t("landing-mockup-embed-live")}
              </Text>
            </Box>
            <Box p="xs">
              <Text size="xs" c="dark.6">
                {t("landing-mockup-embed-chat")}
              </Text>
            </Box>
          </Box>
        </Box>
      </>
    );
  }

  if (activeSection === "whatsapp") {
    return (
      <>
        <Box
          p={headerP}
          style={{
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            background: "rgba(37, 211, 102, 0.15)",
          }}
        >
          <Group gap="xs">
            <Box
              w={8}
              h={8}
              style={{ borderRadius: 4, background: "#25d366" }}
            />
            <Text size="xs" c="dimmed" fw={600}>
              {t("landing-mockup-whatsapp-title")}
            </Text>
          </Group>
        </Box>
        <Stack gap={stackGap} p={stackP} style={{ flex: 1 }}>
          <Box p="xs" style={{ ...bubbleStyle("start"), background: "#e7f5ec" }}>
            <Text size="xs" c="dark.7">
              {t("landing-mockup-whatsapp-in")}
            </Text>
          </Box>
          <Box
            p="xs"
            style={{
              ...bubbleStyle("end"),
              background: "rgba(139, 92, 246, 0.25)",
              border: "1px solid rgba(139, 92, 246, 0.3)",
            }}
          >
            <Text size="xs" c="gray.2">
              {t("landing-mockup-whatsapp-out")}
            </Text>
          </Box>
        </Stack>
      </>
    );
  }

  if (activeSection === "media") {
    return (
      <>
        <Box
          p={headerP}
          style={{
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            background: "rgba(0,0,0,0.2)",
          }}
        >
          <Group gap="xs">
            <Box
              w={8}
              h={8}
              style={{ borderRadius: 4, background: "#8b5cf6" }}
            />
            <Text size="xs" c="dimmed" fw={600}>
              {t("landing-mockup-media-title")}
            </Text>
          </Group>
        </Box>
        <Stack gap={stackGap} p={stackP} style={{ flex: 1 }} justify="center">
          <Box ta="center" mb="xs">
            <motion.div
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <Text size="xs" c="dimmed" fw={500}>
                {t("landing-mockup-media-processing")}
              </Text>
            </motion.div>
          </Box>
          <Group gap="sm" justify="center" wrap="wrap">
            {["landing-mockup-media-image", "landing-mockup-media-doc", "landing-mockup-media-transcription"].map(
              (key, i) => (
                <motion.div
                  key={key}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * 0.15, duration: 0.3 }}
                >
                  <Box
                    p="sm"
                    style={{
                      borderRadius: 12,
                      background: "rgba(139, 92, 246, 0.2)",
                      border: "1px solid rgba(139, 92, 246, 0.3)",
                      minWidth: 80,
                      textAlign: "center",
                    }}
                  >
                    <Text size="xs" c="violet.3" fw={600}>
                      {t(key)}
                    </Text>
                  </Box>
                </motion.div>
              )
            )}
          </Group>
        </Stack>
      </>
    );
  }

  // Default: chat
  return (
    <>
      <Box
        p={headerP}
        style={{
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          background: "rgba(0,0,0,0.2)",
        }}
      >
        <Group gap="xs">
          <Box w={8} h={8} style={{ borderRadius: 4, background: "#8b5cf6" }} />
          <Text size="xs" c="dimmed" fw={600}>
            {t("landing-mockup-title")}
          </Text>
        </Group>
      </Box>
      <Stack gap={stackGap} p={stackP} style={{ flex: 1 }}>
        <Box p="xs" style={{ ...bubbleStyle("start") }}>
          <Text size="xs" c="gray.3">
            {t("landing-mockup-chat-1")}
          </Text>
        </Box>
        <Box
          p="xs"
          style={{
            ...bubbleStyle("end"),
            background: "rgba(139, 92, 246, 0.15)",
            border: "1px solid rgba(139, 92, 246, 0.2)",
          }}
        >
          <Text size="xs" c="gray.2">
            {t("landing-mockup-chat-2")}
          </Text>
        </Box>
        {!compact && (
          <Box p="xs" style={{ ...bubbleStyle("start") }}>
            <Text size="xs" c="gray.3">
              {t("landing-mockup-chat-3")}
            </Text>
          </Box>
        )}
        {/* Typing indicator */}
        <Box p="xs" style={{ ...bubbleStyle("start"), alignSelf: "flex-start" }}>
          <Group gap={4}>
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: "var(--mantine-color-violet-5)",
                }}
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{
                  duration: 1,
                  repeat: Infinity,
                  delay: i * 0.2,
                }}
              />
            ))}
          </Group>
        </Box>
      </Stack>
      <Box
        p={inputP}
        style={{
          borderTop: "1px solid rgba(255,255,255,0.06)",
          background: "rgba(0,0,0,0.15)",
        }}
      >
        <Box
          py={8}
          px={12}
          style={{
            borderRadius: 12,
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <Text size="xs" c="dimmed">
            {t("landing-mockup-placeholder")}
          </Text>
        </Box>
      </Box>
    </>
  );
};

const StickyMockup = ({
  scrollYProgress,
  compact = false,
}: {
  scrollYProgress: ReturnType<typeof useScroll>["scrollYProgress"];
  compact?: boolean;
}) => {
  const [activeSection, setActiveSection] = useState<MockupSection>("chat");

  useMotionValueEvent(scrollYProgress, "change", (v) => {
    setActiveSection(getMockupSection(v));
  });

  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001,
  });
  const rotateY = useTransform(smoothProgress, [0, 0.5, 1], [10, 0, -10]);
  const scale = useTransform(smoothProgress, [0, 0.5, 1], [0.9, 1, 0.9]);

  return (
    <Box
      style={{
        position: "sticky",
        top: compact ? "8vh" : "clamp(80px, 15vh, 140px)",
        height: compact ? "38vh" : "70vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        perspective: compact ? 800 : 1200,
      }}
    >
      <motion.div
        style={{
          rotateY: compact ? undefined : rotateY,
          scale,
          width: "100%",
          maxWidth: compact ? 280 : 480,
          aspectRatio: "4/3",
          background: "rgba(255, 255, 255, 0.03)",
          backdropFilter: "blur(16px)",
          WebkitBackdropFilter: "blur(16px)",
          borderRadius: 24,
          border: "1px solid rgba(139, 92, 246, 0.3)",
          boxShadow:
            "0 50px 100px -20px rgba(0,0,0,0.6), 0 0 40px rgba(139, 92, 246, 0.15), inset 0 1px 0 rgba(255,255,255,0.05), inset 0 0 0 1px rgba(139, 92, 246, 0.1)",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={activeSection}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}
          >
            <MockupContent activeSection={activeSection} compact={compact} />
          </motion.div>
        </AnimatePresence>
      </motion.div>
    </Box>
  );
};

export const Landing = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const isMobile = useMediaQuery("(max-width: 900px)");

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  const handleGetStarted = () => {
    const signupUrl = DEFAULT_ORGANIZATION_ID
      ? `/signup?orgId=${DEFAULT_ORGANIZATION_ID}`
      : "/signup";
    navigate(signupUrl);
  };

  return (
    <Box
      style={{
        minHeight: "100vh",
        background:
          "radial-gradient(ellipse 100% 80% at 50% -10%, rgba(67, 56, 202, 0.4) 0%, transparent 55%), radial-gradient(circle at 80% 90%, rgba(139, 92, 246, 0.12) 0%, transparent 50%), radial-gradient(circle at 20% 30%, rgba(88, 28, 135, 0.15) 0%, transparent 50%), #050508",
        // overflowX: "clip",
      }}
    >
      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: "easeOut" }}
      >
        <Box component="section" py={{ base: 60, md: 100 }} px="md">
          <Stack align="center" gap="xl" maw={900} mx="auto">
            <Title
              order={1}
              ta="center"
              size="clamp(2.25rem, 5vw, 4rem)"
              fw={900}
              lh={1.2}
              style={{ letterSpacing: "-0.05em" }}
            >
              {t("welcome-to-masscer")}{" "}
              <Text
                component="span"
                inherit
                fw={800}
                c="violet.4"
                style={{
                  background:
                    "linear-gradient(135deg, var(--mantine-color-violet-4) 0%, var(--mantine-color-violet-6) 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }}
              >
                Masscer AI
              </Text>
            </Title>
            <Text
              size="lg"
              ta="center"
              maw={720}
              c="dimmed"
              lh={1.7}
              style={{ lineHeight: 1.75 }}
            >
              {t("landing-hero-description")}
            </Text>
            <Stack align="center" gap={4}>
              <Button
                component={motion.button}
                size="xl"
                variant="gradient"
                gradient={{ from: "violet.6", to: "violet.8" }}
                leftSection={<IconSparkles size={22} />}
                onClick={handleGetStarted}
                px={40}
                animate={{
                  boxShadow: [
                    "0 0 20px rgba(139, 92, 246, 0.3)",
                    "0 0 30px rgba(139, 92, 246, 0.5)",
                    "0 0 20px rgba(139, 92, 246, 0.3)",
                  ],
                }}
                transition={{ duration: 3, repeat: Infinity }}
                whileHover={{
                  scale: 1.05,
                  boxShadow: "0 0 25px rgba(139, 92, 246, 0.5)",
                }}
                whileTap={{ scale: 0.98 }}
              >
                {t("get-started")}
              </Button>
              <Text size="xs" c="dimmed">
                {t("no-credit-card-required")}
              </Text>
            </Stack>
          </Stack>
        </Box>
      </motion.div>

      {/* Sticky showcase (desktop) | Vertical feature+mockup (mobile) */}
      {isMobile ? (
        <MobileFeaturesVertical />
      ) : (
        <Box
          ref={containerRef}
          style={{ position: "relative", minHeight: "500vh" }}
        >
          <Box maw={1200} mx="auto" px="lg" pb={120}>
            <Flex gap={60} align="flex-start" wrap="nowrap">
              {/* Left: Sticky mockup - same height as right for 1:1 scroll mapping */}
              <Box
                style={{
                  flex: "0 0 45%",
                  minWidth: 320,
                  minHeight: "500vh",
                  position: "relative",
                  alignSelf: "stretch",
                }}
              >
                <StickyMockup scrollYProgress={scrollYProgress} />
              </Box>

              {/* Right: Scrolling features */}
              <Box style={{ flex: "1 1 55%", minWidth: 0 }}>
                {FEATURES.map((f) => (
                  <FeatureScrollBlock
                    key={f.titleKey}
                    titleKey={f.titleKey}
                    descKey={f.descKey}
                  />
                ))}
                <GenerateMediaBlock />
              </Box>
            </Flex>
          </Box>
        </Box>
      )}
    </Box>
  );
};

const FeatureScrollBlock = ({
  titleKey,
  descKey,
  mobile = false,
}: {
  titleKey: string;
  descKey: string;
  mobile?: boolean;
}) => {
  const { t } = useTranslation();
  return (
    <Box
      style={{
        minHeight: mobile ? "70vh" : "100vh",
        display: "flex",
        alignItems: "center",
        paddingRight: mobile ? 0 : 24,
        paddingLeft: mobile ? 0 : 0,
      }}
    >
      <Stack gap="md">
        <Title
          order={2}
          size={mobile ? "h2" : "h1"}
          c={mobile ? "violet.3" : undefined}
          fw={800}
          ta={mobile ? "center" : undefined}
          style={
            mobile
              ? undefined
              : {
                  background:
                    "linear-gradient(135deg, var(--mantine-color-violet-3) 0%, var(--mantine-color-white) 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }
          }
        >
          {t(titleKey)}
        </Title>
        <Text
          size={mobile ? "md" : "lg"}
          c="dimmed"
          lh={1.7}
          maw={mobile ? undefined : 520}
          ta={mobile ? "center" : undefined}
        >
          {t(descKey)}
        </Text>
      </Stack>
    </Box>
  );
};

const GenerateMediaBlock = ({ mobile = false }: { mobile?: boolean } = {}) => {
  const { t } = useTranslation();
  return (
    <Box
      style={{
        minHeight: mobile ? "70vh" : "100vh",
        display: "flex",
        alignItems: "center",
        paddingRight: mobile ? 0 : 24,
      }}
    >
      <Stack gap="md" align={mobile ? "center" : "flex-start"}>
        <Group gap="xs" justify={mobile ? "center" : "flex-start"}>
          <Box
            p="sm"
            style={{
              borderRadius: 12,
              background:
                "linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(139, 92, 246, 0.06) 100%)",
              border: "1px solid rgba(139, 92, 246, 0.3)",
            }}
          >
            <IconPhoto size={32} color="var(--mantine-color-violet-5)" />
          </Box>
          <Title
            order={2}
            size={mobile ? "h2" : "h1"}
            c={mobile ? "violet.3" : undefined}
            fw={800}
            style={
              mobile
                ? { textAlign: "center" }
                : {
                    background:
                      "linear-gradient(135deg, var(--mantine-color-violet-3) 0%, var(--mantine-color-white) 100%)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                    backgroundClip: "text",
                  }
            }
          >
            {t("landing-generate-media-title")}
          </Title>
        </Group>
        <Text
          size={mobile ? "md" : "lg"}
          c="dimmed"
          lh={1.7}
          maw={mobile ? undefined : 520}
          ta={mobile ? "center" : undefined}
        >
          {t("landing-generate-media-description")}
        </Text>
        <Group gap="sm" mt="sm" justify={mobile ? "center" : undefined}>
          {[
            "landing-tag-videos",
            "landing-tag-images",
            "landing-tag-documents",
            "landing-tag-transcriptions",
          ].map((key) => (
            <Card key={key} padding="sm" withBorder radius="md">
              <Text size="sm" fw={500}>
                {t(key)}
              </Text>
            </Card>
          ))}
        </Group>
      </Stack>
    </Box>
  );
};

/** Inline mockup for mobile: each feature card is followed by its visual */
const InlineMockup = ({ section }: { section: MockupSection }) => {
  return (
    <Box
      style={{
        width: "100%",
        maxWidth: 280,
        margin: "0 auto",
        aspectRatio: "4/3",
        background: "rgba(255, 255, 255, 0.03)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        borderRadius: 24,
        border: "1px solid rgba(139, 92, 246, 0.3)",
        boxShadow:
          "0 24px 48px -12px rgba(0,0,0,0.5), 0 0 24px rgba(139, 92, 246, 0.1)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <MockupContent activeSection={section} compact />
    </Box>
  );
};

const MobileFeaturesVertical = () => {
  const sections: MockupSection[] = ["chat", "alerts", "embed", "whatsapp", "media"];
  return (
    <Stack gap="xl" maw={500} mx="auto" px="md" pb={100}>
      {FEATURES.map((f, i) => (
        <Stack key={f.titleKey} gap="lg" align="center">
          <FeatureScrollBlock
            titleKey={f.titleKey}
            descKey={f.descKey}
            mobile
          />
          <InlineMockup section={sections[i]} />
        </Stack>
      ))}
      <Stack gap="lg" align="center">
        <GenerateMediaBlock mobile />
        <InlineMockup section="media" />
      </Stack>
    </Stack>
  );
};
