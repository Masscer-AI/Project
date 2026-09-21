import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Box,
  Button,
  Group,
  Loader,
  Pagination,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconArrowLeft, IconMenu2, IconSearch } from "@tabler/icons-react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import {
  getOrganizationList,
  getOrganizationListRecords,
  getUserOrganizations,
} from "../../modules/apiCalls";
import type { TOrganizationList, TOrganizationListRecord } from "../../types";

const PAGE_SIZE = 50;
const SEARCH_DEBOUNCE_MS = 300;

export default function ListDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { listId } = useParams<{ listId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));

  const [orgId, setOrgId] = useState<string | null>(
    searchParams.get("organization")
  );
  const [list, setList] = useState<TOrganizationList | null>(null);
  const [records, setRecords] = useState<TOrganizationListRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState(searchParams.get("q") || "");
  const [debouncedQuery, setDebouncedQuery] = useState(
    (searchParams.get("q") || "").trim()
  );
  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10) || 1);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedQuery(searchInput.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [searchInput]);

  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (debouncedQuery) next.set("q", debouncedQuery);
    else next.delete("q");
    const currentQ = (searchParams.get("q") || "").trim();
    if (currentQ !== debouncedQuery) {
      next.set("page", "1");
    }
    if (orgId) next.set("organization", orgId);
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true });
    }
  }, [debouncedQuery, orgId, searchParams, setSearchParams]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (orgId) return;
      try {
        const orgs = await getUserOrganizations();
        if (!cancelled && orgs[0]) setOrgId(String(orgs[0].id));
      } catch {
        if (!cancelled) toast.error(t("error-loading-organizations"));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [orgId, t]);

  const load = useCallback(async () => {
    if (!orgId || !listId) return;
    setLoading(true);
    try {
      const [{ list: detail }, recordsResp] = await Promise.all([
        getOrganizationList(orgId, listId),
        getOrganizationListRecords(
          orgId,
          listId,
          page,
          PAGE_SIZE,
          debouncedQuery
        ),
      ]);
      setList(detail);
      setRecords(recordsResp.records || []);
      setTotal(recordsResp.total || 0);
    } catch {
      toast.error(t("org-list-preview-error"));
      setList(null);
      setRecords([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [orgId, listId, page, debouncedQuery, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const columns = useMemo(() => {
    const configCols =
      list?.config?.columns?.map((c) => c.name).filter(Boolean) ?? [];
    if (configCols.length > 0) return configCols;
    if (records[0]?.data) return Object.keys(records[0].data);
    return [];
  }, [list, records]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const setPage = (nextPage: number) => {
    const next = new URLSearchParams(searchParams);
    next.set("page", String(nextPage));
    if (orgId) next.set("organization", orgId);
    setSearchParams(next);
  };

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
        }}
        className="relative"
      >
        {!chatState.isSidebarOpened && (
          <Box pos="absolute" top={24} left={24} style={{ zIndex: 10 }}>
            <ActionIcon
              variant="subtle"
              color="gray"
              onClick={toggleSidebar}
              aria-label={t("open-sidebar")}
            >
              <IconMenu2 size={20} />
            </ActionIcon>
          </Box>
        )}

        <Box w="100%" maw="80rem" mx="auto">
          <Stack gap="md">
            <Group>
              <Button
                variant="subtle"
                color="gray"
                leftSection={<IconArrowLeft size={16} />}
                onClick={() => {
                  const params = new URLSearchParams({ activeTab: "lists" });
                  if (orgId) params.set("organization", orgId);
                  navigate(`/knowledge-base?${params.toString()}`);
                }}
              >
                {t("org-list-back")}
              </Button>
            </Group>
            <div>
              <Title order={2}>
                {list?.name || t("org-list-preview-title", { name: "" })}
              </Title>
              {list?.description ? (
                <Text c="dimmed" size="sm" mt={4}>
                  {list.description}
                </Text>
              ) : null}
              {list ? (
                <Text size="xs" c="dimmed" mt={4}>
                  {list.original_filename} · {list.record_count}{" "}
                  {t("org-list-records-label")}
                </Text>
              ) : null}
            </div>

            <TextInput
              leftSection={<IconSearch size={16} />}
              placeholder={t("org-list-search-placeholder")}
              value={searchInput}
              onChange={(e) => setSearchInput(e.currentTarget.value)}
            />

            {loading ? (
              <Group justify="center" py="xl">
                <Loader color="violet" />
              </Group>
            ) : records.length === 0 || columns.length === 0 ? (
              <Text c="dimmed">
                {debouncedQuery
                  ? t("org-list-search-empty")
                  : t("org-list-preview-empty")}
              </Text>
            ) : (
              <Stack gap="sm">
                <Text size="xs" c="dimmed">
                  {t("org-list-preview-showing", {
                    shown: records.length,
                    total,
                  })}
                </Text>
                <Table.ScrollContainer minWidth={480}>
                  <Table
                    striped
                    highlightOnHover
                    withTableBorder
                    withColumnBorders
                    layout="auto"
                    style={{ width: "max-content", minWidth: "100%" }}
                  >
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th w={48} style={{ whiteSpace: "nowrap" }}>
                          #
                        </Table.Th>
                        {columns.map((col) => (
                          <Table.Th key={col} style={{ whiteSpace: "nowrap" }}>
                            {col}
                          </Table.Th>
                        ))}
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {records.map((row) => (
                        <Table.Tr key={row.id}>
                          <Table.Td>{row.position}</Table.Td>
                          {columns.map((col) => (
                            <Table.Td
                              key={col}
                              style={{
                                whiteSpace: "normal",
                                overflowWrap: "anywhere",
                              }}
                            >
                              {row.data[col] ?? ""}
                            </Table.Td>
                          ))}
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Table.ScrollContainer>
                {pageCount > 1 ? (
                  <Group justify="center">
                    <Pagination
                      total={pageCount}
                      value={page}
                      onChange={setPage}
                    />
                  </Group>
                ) : null}
              </Stack>
            )}
          </Stack>
        </Box>
      </div>
    </main>
  );
}
