import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Checkbox,
  ColorSwatch,
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
  color?: string;
};

function TagSwatch({ color }: { color?: string }) {
  if (!color) return null;
  return <ColorSwatch color={color} size={10} />;
}

type Props = {
  label: string;
  description?: string;
  placeholder?: string;
  value: string[];
  onChange: (value: string[]) => void;
  data: MultiSelectOption[];
  disabled?: boolean;
  pickerTitle?: string;
};

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
  const [activeIndex, setActiveIndex] = useState(0);
  const activeRowRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return data;
    return data.filter((d) => d.label.toLowerCase().includes(q));
  }, [data, filter]);

  const highlighted =
    filtered.length === 0 ? -1 : Math.min(activeIndex, filtered.length - 1);

  useEffect(() => {
    activeRowRef.current?.scrollIntoView({ block: "nearest" });
  }, [highlighted]);

  const finish = () => {
    setFilter("");
    setActiveIndex(0);
    close();
  };

  const toggleValue = (optionValue: string, checked: boolean) => {
    if (checked) {
      if (!value.includes(optionValue)) {
        onChange([...value, optionValue]);
      }
      return;
    }
    onChange(value.filter((v) => v !== optionValue));
  };

  const onSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (highlighted < 0) return;
      setActiveIndex(Math.min(highlighted + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (highlighted < 0) return;
      setActiveIndex(Math.max(highlighted - 1, 0));
    } else if (e.key === " ") {
      e.preventDefault();
      if (highlighted < 0) return;
      const opt = filtered[highlighted];
      toggleValue(opt.value, !value.includes(opt.value));
    } else if (e.key === "Enter") {
      e.preventDefault();
      finish();
    }
  };

  const selected = value
    .map((v) => data.find((d) => d.value === v))
    .filter((opt): opt is MultiSelectOption => Boolean(opt));

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
        renderOption={({ option }) => {
          const color = data.find((d) => d.value === option.value)?.color;
          return (
            <Group gap={8} wrap="nowrap">
              <TagSwatch color={color} />
              <Text size="sm">{option.label}</Text>
            </Group>
          );
        }}
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
        {selected.length > 0 && (
          <Group gap={6}>
            {selected.map((opt) => (
              <Badge
                key={opt.value}
                variant="light"
                color="gray"
                size="sm"
                leftSection={opt.color ? <TagSwatch color={opt.color} /> : undefined}
              >
                {opt.label}
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
        onClose={finish}
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
            data-autofocus
            placeholder={t("search")}
            leftSection={<IconSearch size={16} />}
            value={filter}
            onChange={(e) => {
              setFilter(e.currentTarget.value);
              setActiveIndex(0);
            }}
            onKeyDown={onSearchKeyDown}
          />
          <ScrollArea.Autosize mah="55vh" type="auto">
            <Stack gap="xs">
              {filtered.length === 0 ? (
                <Text size="sm" c="dimmed" ta="center" py="md">
                  {t("multiselect-no-matches")}
                </Text>
              ) : (
                filtered.map((opt, index) => (
                  <Box
                    key={opt.value}
                    ref={index === highlighted ? activeRowRef : undefined}
                    py={6}
                    px={6}
                    style={{
                      borderBottom: "1px solid var(--mantine-color-dark-4)",
                      borderRadius: 6,
                      background:
                        index === highlighted
                          ? "var(--mantine-color-violet-light)"
                          : undefined,
                    }}
                    onClick={() => setActiveIndex(index)}
                  >
                    <Checkbox
                      label={
                        <Group gap={8} wrap="nowrap">
                          <TagSwatch color={opt.color} />
                          <span>{opt.label}</span>
                        </Group>
                      }
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
          <Button fullWidth onClick={finish}>
            {t("finish")}
          </Button>
        </Stack>
      </Drawer>
    </>
  );
};
