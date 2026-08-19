import React, { useEffect, useMemo, useState } from "react";
import { Accordion, Button, Group, Stack, Text } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { getAgentToolGroups } from "../../modules/apiCalls";
import type { TMCPToolPresetGroup } from "../../modules/apiCalls";
import { mcpToolGroupLabel } from "../../utils/mcpToolGroupLabel";
import { CapabilitiesChecklist } from "../CapabilitiesChecklist/CapabilitiesChecklist";

export type ToolsSelectorContentProps = {
  description?: string;
  value: string[];
  onChange: (names: string[]) => void;
  requiredNames?: readonly string[];
  disabledOffNames?: readonly string[];
  disabledOffHint?: (name: string) => string;
  loadGroups?: boolean;
  toolGroups?: TMCPToolPresetGroup[];
  onGroupsLoaded?: (groups: TMCPToolPresetGroup[]) => void;
};

export function ToolsSelectorContent({
  description,
  value,
  onChange,
  requiredNames = [],
  disabledOffNames = [],
  disabledOffHint,
  loadGroups = true,
  toolGroups: toolGroupsProp,
  onGroupsLoaded,
}: ToolsSelectorContentProps) {
  const { t } = useTranslation();
  const [loadedGroups, setLoadedGroups] = useState<TMCPToolPresetGroup[]>([]);
  const toolGroups = toolGroupsProp ?? loadedGroups;

  useEffect(() => {
    if (!loadGroups) return;
    getAgentToolGroups()
      .then((res) => {
        const groups = res.groups ?? [];
        setLoadedGroups(groups);
        onGroupsLoaded?.(groups);
      })
      .catch(() => {
        setLoadedGroups([]);
        onGroupsLoaded?.([]);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadGroups]);

  const selected = useMemo(() => new Set(value), [value]);
  const requiredSet = useMemo(() => new Set(requiredNames), [requiredNames]);
  const disabledOffSet = useMemo(
    () => new Set(disabledOffNames),
    [disabledOffNames]
  );

  const allToolNames = useMemo(
    () => toolGroups.flatMap((g) => g.items),
    [toolGroups]
  );

  const selectableNames = useMemo(
    () =>
      allToolNames.filter(
        (n) => !requiredSet.has(n) && !disabledOffSet.has(n)
      ),
    [allToolNames, requiredSet, disabledOffSet]
  );

  const allSelected =
    selectableNames.length > 0 &&
    selectableNames.every((name) => selected.has(name));

  const applyNames = (names: string[]) => {
    const next = new Set<string>();
    for (const name of names) {
      if (disabledOffSet.has(name)) continue;
      next.add(name);
    }
    for (const name of requiredNames) next.add(name);
    onChange(Array.from(next));
  };

  return (
    <Stack gap="xs">
      {description ? (
        <Text size="xs" c="dimmed">
          {description}
        </Text>
      ) : null}
      {allToolNames.length > 0 ? (
        <Group justify="flex-end" gap="xs">
          <Button
            size="xs"
            variant="subtle"
            disabled={allSelected}
            onClick={() => applyNames([...selectableNames, ...requiredNames])}
          >
            {t("select-all")}
          </Button>
          <Button
            size="xs"
            variant="subtle"
            color="gray"
            onClick={() => applyNames([...requiredNames])}
          >
            {t("unselect-all")}
          </Button>
        </Group>
      ) : null}
      <Accordion multiple defaultValue={toolGroups.map((g) => g.group)}>
        {toolGroups.map((group) => (
          <Accordion.Item key={group.group} value={group.group}>
            <Accordion.Control>
              {mcpToolGroupLabel(group.group, t)}
            </Accordion.Control>
            <Accordion.Panel>
              <CapabilitiesChecklist
                names={group.items}
                showBulkActions={false}
                requiredNames={requiredNames}
                disabledOffNames={disabledOffNames}
                disabledOffHint={disabledOffHint}
                value={Object.fromEntries(
                  group.items.map((name) => [
                    name,
                    disabledOffSet.has(name)
                      ? false
                      : requiredSet.has(name) || selected.has(name),
                  ])
                )}
                onChange={(next) => {
                  const nextSelected = new Set(selected);
                  for (const name of group.items) {
                    if (disabledOffSet.has(name)) {
                      nextSelected.delete(name);
                      continue;
                    }
                    if (requiredSet.has(name) || next[name]) {
                      nextSelected.add(name);
                    } else {
                      nextSelected.delete(name);
                    }
                  }
                  for (const name of requiredNames) nextSelected.add(name);
                  onChange(Array.from(nextSelected));
                }}
              />
            </Accordion.Panel>
          </Accordion.Item>
        ))}
      </Accordion>
    </Stack>
  );
}
