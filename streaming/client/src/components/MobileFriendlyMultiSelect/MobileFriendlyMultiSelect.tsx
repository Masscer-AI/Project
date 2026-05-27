import React, { useMemo, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Checkbox,
  Drawer,
  Group,
  MultiSelect,
  ScrollArea,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { useDisclosure, useMediaQuery } from "@mantine/hooks";
import { IconChevronDown, IconSearch } from "@tabler/icons-react";
import { useTranslation } from "react-i18next";

export type MultiSelectOption = {
  value: string;
  label: string;
};

type Props = {
  label: string;
  description?: string;
  placeholder?: string;
  value: string[];
  onChange: (value: string[]) => void;
  data: MultiSelectOption[];
  disabled?: boolean;
  /** Shown on the mobile drawer trigger button. */
  pickerTitle?: string;
};

/** MultiSelect that uses a bottom drawer on narrow viewports (avoids keyboard vs dropdown fights). */
export const MobileFriendlyMultiSelect = ({
  label,
  description,
  placeholder,
  value,
  onChange,
  data,
  disabled = false,
  pickerTitle,
}: Props) => {
  const { t } = useTranslation();
  const isMobile = useMediaQuery("(max-width: 48em)");
  const [opened, { open, close }] = useDisclosure(false);
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return data;
    return data.filter((d) => d.label.toLowerCase().includes(q));
  }, [data, filter]);

  const toggleValue = (optionValue: string, checked: boolean) => {
    if (checked) {
      if (!value.includes(optionValue)) {
        onChange([...value, optionValue]);
      }
      return;
    }
    onChange(value.filter((v) => v !== optionValue));
  };

  const selectedLabels = value
    .map((v) => data.find((d) => d.value === v)?.label)
    .filter(Boolean) as string[];

  if (!isMobile) {
    return (
      <MultiSelect
        label={label}
        description={description}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        data={data}
        searchable
        clearable
        disabled={disabled}
        maxDropdownHeight={220}
        comboboxProps={{
          withinPortal: false,
          hideDetached: false,
          zIndex: 400,
          middlewares: { flip: true, shift: true },
        }}
      />
    );
  }

  return (
    <>
      <Stack gap={6}>
        <Text size="sm" fw={500}>
          {label}
        </Text>
        {description && (
          <Text size="xs" c="dimmed">
            {description}
          </Text>
        )}
        {selectedLabels.length > 0 && (
          <Group gap={6}>
            {selectedLabels.map((name) => (
              <Badge key={name} variant="light" color="gray" size="sm">
                {name}
              </Badge>
            ))}
          </Group>
        )}
        <Button
          variant="default"
          size="sm"
          fullWidth
          justify="space-between"
          rightSection={<IconChevronDown size={16} />}
          onClick={open}
          disabled={disabled}
        >
          {value.length > 0
            ? t("multi-select-mobile-summary", { count: value.length })
            : placeholder || pickerTitle || label}
        </Button>
      </Stack>

      <Drawer
        opened={opened}
        onClose={() => {
          setFilter("");
          close();
        }}
        title={pickerTitle || label}
        position="bottom"
        size="85%"
        zIndex={500}
        styles={{
          content: {
            borderTopLeftRadius: "var(--mantine-radius-lg)",
            borderTopRightRadius: "var(--mantine-radius-lg)",
          },
        }}
      >
        <Stack gap="sm" pb="md">
          <TextInput
            placeholder={t("search")}
            leftSection={<IconSearch size={16} />}
            value={filter}
            onChange={(e) => setFilter(e.currentTarget.value)}
          />
          <ScrollArea.Autosize mah="55vh" type="auto">
            <Stack gap="xs">
              {filtered.length === 0 ? (
                <Text size="sm" c="dimmed" ta="center" py="md">
                  {t("multiselect-no-matches")}
                </Text>
              ) : (
                filtered.map((opt) => (
                  <Box
                    key={opt.value}
                    py={6}
                    style={{
                      borderBottom: "1px solid var(--mantine-color-dark-4)",
                    }}
                  >
                    <Checkbox
                      label={opt.label}
                      checked={value.includes(opt.value)}
                      onChange={(e) =>
                        toggleValue(opt.value, e.currentTarget.checked)
                      }
                    />
                  </Box>
                ))
              )}
            </Stack>
          </ScrollArea.Autosize>
          <Button
            fullWidth
            onClick={() => {
              setFilter("");
              close();
            }}
          >
            {t("finish")}
          </Button>
        </Stack>
      </Drawer>
    </>
  );
};
