import React, { useMemo } from "react";
import { Button, Checkbox, Group, Stack, Text } from "@mantine/core";
import { useTranslation } from "react-i18next";

export type CapabilitiesChecklistProps = {
  names: readonly string[];
  value: Record<string, boolean>;
  onChange: (next: Record<string, boolean>) => void;
  requiredNames?: readonly string[];
  disabledOffNames?: readonly string[];
  disabledOffHint?: (name: string) => string;
  label?: string;
  showBulkActions?: boolean;
  titleKey?: (name: string) => string;
  descriptionKey?: (name: string) => string;
};

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
