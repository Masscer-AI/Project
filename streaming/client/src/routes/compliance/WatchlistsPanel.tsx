import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  NativeSelect,
  Stack,
  Table,
  Text,
  TextInput,
} from "@mantine/core";
import { IconSearch } from "@tabler/icons-react";
import {
  listComplianceWatchlists,
  searchComplianceWatchlists,
  TWatchlistHit,
  TWatchlistSummary,
} from "../../modules/apiCalls";

function listLabel(t: (key: string, options?: { defaultValue: string }) => string, slug: string) {
  return t(`compliance-watchlist-${slug}`, { defaultValue: slug });
}

function formatWhen(value: string, language: string) {
  return new Date(value).toLocaleString(language);
}

function sourceDate(value: string, language: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return date.toLocaleDateString(language, {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

function situationColor(value: string) {
  const folded = value.toLowerCase();
  if (folded.includes("definitiv")) return "red";
  if (folded.includes("presunt")) return "orange";
  if (folded.includes("desvirtu") || folded.includes("favorable")) return "gray";
  return "yellow";
}

export function WatchlistsPanel() {
  const { t, i18n } = useTranslation();
  const [lists, setLists] = useState<TWatchlistSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [listSlug, setListSlug] = useState("");
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [truncated, setTruncated] = useState(false);
  const [hits, setHits] = useState<TWatchlistHit[]>([]);

  useEffect(() => {
    void (async () => {
      try {
        const data = await listComplianceWatchlists();
        setLists(data.results);
      } catch {
        toast.error(t("compliance-watchlists-load-error"));
      } finally {
        setLoading(false);
      }
    })();
  }, [t]);

  const runSearch = async () => {
    const text = query.trim();
    if (text.length < 3) {
      toast.error(t("compliance-watchlists-query-short"));
      return;
    }
    setSearching(true);
    try {
      const data = await searchComplianceWatchlists(text, listSlug);
      setHits(data.results);
      setTruncated(data.truncated);
      setSearched(true);
    } catch {
      toast.error(t("compliance-watchlists-search-error"));
    } finally {
      setSearching(false);
    }
  };

  if (loading) {
    return (
      <Stack align="center" py="xl">
        <Loader color="violet" size="sm" />
      </Stack>
    );
  }

  return (
    <Stack gap="lg">
      <Text size="sm" c="dimmed">
        {t("compliance-watchlists-help")}
      </Text>
      <Card withBorder p={0}>
        <Table.ScrollContainer minWidth={640}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t("compliance-watchlists-col-list")}</Table.Th>
                <Table.Th>{t("compliance-watchlists-col-rows")}</Table.Th>
                <Table.Th>{t("compliance-watchlists-col-updated")}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {lists.map((row) => (
                <Table.Tr key={row.list_slug}>
                  <Table.Td>{listLabel(t, row.list_slug)}</Table.Td>
                  <Table.Td>
                    {row.record_count.toLocaleString(i18n.language)}
                  </Table.Td>
                  <Table.Td style={{ whiteSpace: "normal" }}>
                    {row.ingested_at ? (
                      <Stack gap={2}>
                        <Text size="sm" style={{ overflowWrap: "anywhere" }}>
                          {row.date_generated
                            ? t("compliance-watchlists-updated", {
                                date: sourceDate(row.date_generated, i18n.language),
                              })
                            : t("compliance-watchlists-downloaded", {
                                date: formatWhen(row.ingested_at, i18n.language),
                              })}
                        </Text>
                        {row.date_generated ? (
                          <Text size="xs" c="dimmed">
                            {t("compliance-watchlists-downloaded", {
                              date: formatWhen(row.ingested_at, i18n.language),
                            })}
                          </Text>
                        ) : null}
                      </Stack>
                    ) : (
                      <Text size="sm" c="dimmed">
                        {t("compliance-watchlists-not-loaded")}
                      </Text>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Card>

      <Card withBorder p="lg">
        <Stack gap="sm">
          <Text size="sm" c="dimmed">
            {t("compliance-watchlists-search-help")}
          </Text>
          <Group align="flex-end" wrap="wrap">
            <TextInput
              label={t("compliance-watchlists-search-label")}
              placeholder={t("compliance-watchlists-search-placeholder")}
              value={query}
              style={{ flex: 1, minWidth: "16rem" }}
              onChange={(e) => {
                const val = e.currentTarget.value;
                setQuery(val);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") void runSearch();
              }}
            />
            <NativeSelect
              label={t("compliance-watchlists-col-list")}
              value={listSlug}
              onChange={(e) => {
                const val = e.currentTarget.value;
                setListSlug(val);
              }}
              data={[
                { value: "", label: t("compliance-watchlists-all") },
                ...lists.map((row) => ({
                  value: row.list_slug,
                  label: listLabel(t, row.list_slug),
                })),
              ]}
            />
            <Button
              leftSection={<IconSearch size={16} />}
              loading={searching}
              onClick={() => void runSearch()}
            >
              {t("compliance-watchlists-search")}
            </Button>
          </Group>
          {searched && hits.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t("compliance-watchlists-empty")}
            </Text>
          ) : null}
          {truncated ? (
            <Alert color="yellow" variant="light">
              {t("compliance-watchlists-truncated")}
            </Alert>
          ) : null}
          {hits.length > 0 ? (
            <Stack gap="sm">
              <Text size="sm" c="dimmed">
                {t("compliance-watchlists-match-note")}
              </Text>
              <Table.ScrollContainer minWidth={720}>
                <Table highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{t("compliance-watchlists-col-name")}</Table.Th>
                      <Table.Th>{t("compliance-watchlists-col-reference")}</Table.Th>
                      <Table.Th>{t("compliance-watchlists-col-list")}</Table.Th>
                      <Table.Th>{t("compliance-watchlists-col-situation")}</Table.Th>
                      <Table.Th>{t("compliance-watchlists-col-listed")}</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {hits.map((hit) => (
                      <Table.Tr key={`${hit.list_slug}-${hit.reference_number}`}>
                        <Table.Td>{hit.primary_name || "—"}</Table.Td>
                        <Table.Td>{hit.reference_number}</Table.Td>
                        <Table.Td>{listLabel(t, hit.list_slug)}</Table.Td>
                        <Table.Td>
                          {hit.situation ? (
                            <Badge
                              variant="light"
                              color={situationColor(hit.situation)}
                              style={{
                                textTransform: "none",
                                height: "auto",
                                whiteSpace: "normal",
                                overflow: "visible",
                              }}
                            >
                              {hit.situation}
                            </Badge>
                          ) : (
                            "—"
                          )}
                        </Table.Td>
                        <Table.Td>{hit.listed_on || "—"}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            </Stack>
          ) : null}
        </Stack>
      </Card>
    </Stack>
  );
}
