import React, { useMemo } from "react";
import { Button, Checkbox, Group, Stack, Text } from "@mantine/core";
import { useTranslation } from "react-i18next";

export type CapabilitiesChecklistProps = {
  /** Tool slugs shown as checkboxes (order preserved). */
  names: readonly string[];
  value: Record<string, boolean>;
  onChange: (next: Record<string, boolean>) => void;
  /** Always enabled; cannot be unchecked; always on after Select all / Clear. */
  requiredNames?: readonly string[];
  /** Always off; cannot be checked (e.g. user-required tools on widgets). */
  disabledOffNames?: readonly string[];
  /** Extra description under a locked-off tool (after the normal description). */
  disabledOffHint?: (name: string) => string;
  /** Optional section title above the list. */
  label?: string;
  /** Show Select all / Unselect all for this list. Default true. */
  showBulkActions?: boolean;
  /** i18n key prefix; default widget-capability-{name}-title/description */
  titleKey?: (name: string) => string;
  descriptionKey?: (name: string) => string;
};

/**
 * Shared checkbox list for agent tool capabilities (WhatsApp lines, chat widgets, …).
 * Uses the same widget-capability-* locale keys across surfaces.
 */
export function CapabilitiesChecklist({
  names,
  value,
  onChange,
  requiredNames = [],
  disabledOffNames = [],
  disabledOffHint,
  label,
  showBulkActions = true,
  titleKey = (name) => `widget-capability-${name}-title`,
  descriptionKey = (name) => `widget-capability-${name}-description`,
}: CapabilitiesChecklistProps) {
  const { t } = useTranslation();
  const requiredSet = useMemo(
    () => new Set(requiredNames),
    [requiredNames]
  );
  const disabledOffSet = useMemo(
    () => new Set(disabledOffNames),
    [disabledOffNames]
  );

  const toggleableNames = useMemo(
    () =>
      names.filter((n) => !requiredSet.has(n) && !disabledOffSet.has(n)),
    [names, requiredSet, disabledOffSet]
  );

  const allToggleableOn =
    toggleableNames.length > 0 &&
    toggleableNames.every((n) => value[n] === true);

  const selectAll = () => {
    const next = { ...value };
    for (const name of names) {
      if (disabledOffSet.has(name)) next[name] = false;
      else next[name] = true;
    }
    onChange(next);
  };

  const unselectAll = () => {
    const next = { ...value };
    for (const name of names) {
      next[name] = requiredSet.has(name);
    }
    onChange(next);
  };

  const showHeader = Boolean(label) || (showBulkActions && toggleableNames.length > 0);

  return (
    <Stack gap="sm">
      {showHeader && (
        <Group justify="space-between" align="center" wrap="wrap" gap="xs">
          {label ? (
            <Text size="sm" fw={500}>
              {label}
            </Text>
          ) : (
            <span />
          )}
          {showBulkActions && toggleableNames.length > 0 ? (
            <Group gap="xs">
              <Button
                size="xs"
                variant="subtle"
                onClick={selectAll}
                disabled={allToggleableOn}
              >
                {t("select-all")}
              </Button>
              <Button
                size="xs"
                variant="subtle"
                color="gray"
                onClick={unselectAll}
              >
                {t("unselect-all")}
              </Button>
            </Group>
          ) : null}
        </Group>
      )}

      <Stack gap="sm">
        {names.map((capName) => {
          const isRequired = requiredSet.has(capName);
          const isLockedOff = disabledOffSet.has(capName);
          const hint = isLockedOff && disabledOffHint
            ? disabledOffHint(capName)
            : "";
          return (
            <Stack key={capName} gap={2}>
              <Checkbox
                label={t(titleKey(capName))}
                checked={isLockedOff ? false : (value[capName] ?? false)}
                disabled={isRequired || isLockedOff}
                onChange={(e) => {
                  if (isRequired || isLockedOff) return;
                  const checked = e.currentTarget.checked;
                  onChange({
                    ...value,
                    [capName]: checked,
                  });
                }}
              />
              <Text size="xs" c="dimmed" ml={28}>
                {t(descriptionKey(capName))}
                {hint ? ` ${hint}` : ""}
              </Text>
            </Stack>
          );
        })}
      </Stack>
    </Stack>
  );
}
