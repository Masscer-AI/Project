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
  /** Optional section title above the list. */
  label?: string;
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
  label,
  titleKey = (name) => `widget-capability-${name}-title`,
  descriptionKey = (name) => `widget-capability-${name}-description`,
}: CapabilitiesChecklistProps) {
  const { t } = useTranslation();
  const requiredSet = useMemo(
    () => new Set(requiredNames),
    [requiredNames]
  );

  const toggleableNames = useMemo(
    () => names.filter((n) => !requiredSet.has(n)),
    [names, requiredSet]
  );

  const allToggleableOn =
    toggleableNames.length > 0 &&
    toggleableNames.every((n) => value[n] === true);

  const selectAll = () => {
    const next = { ...value };
    for (const name of names) next[name] = true;
    onChange(next);
  };

  const unselectAll = () => {
    const next = { ...value };
    for (const name of names) {
      next[name] = requiredSet.has(name);
    }
    onChange(next);
  };

  return (
    <Stack gap="sm">
      {(label || toggleableNames.length > 0) && (
        <Group justify="space-between" align="center" wrap="wrap" gap="xs">
          {label ? (
            <Text size="sm" fw={500}>
              {label}
            </Text>
          ) : (
            <span />
          )}
          {toggleableNames.length > 0 ? (
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
          return (
            <Stack key={capName} gap={2}>
              <Checkbox
                label={t(titleKey(capName))}
                checked={value[capName] ?? false}
                disabled={isRequired}
                onChange={(e) => {
                  if (isRequired) return;
                  const checked = e.currentTarget.checked;
                  onChange({
                    ...value,
                    [capName]: checked,
                  });
                }}
              />
              <Text size="xs" c="dimmed" ml={28}>
                {t(descriptionKey(capName))}
              </Text>
            </Stack>
          );
        })}
      </Stack>
    </Stack>
  );
}
