import { Group, Select, TextInput } from "@mantine/core";
import { COUNTRY_DIAL_CODES } from "../../utils/countryDialCodes";
import classes from "./PhoneField.module.css";

function flagUrl(iso: string) {
  return `https://flagcdn.com/24x18/${iso.toLowerCase()}.png`;
}

const OPTIONS = (() => {
  const rows = COUNTRY_DIAL_CODES.map((country) => ({
    value: country.value,
    label: `${country.name} (+${country.dial})`,
  }));
  const mexico = rows.find((row) => row.value === "MX");
  const rest = rows.filter((row) => row.value !== "MX");
  return mexico ? [mexico, ...rest] : rows;
})();

export function PhoneField({
  label,
  country,
  national,
  onChange,
}: {
  label: string;
  country: string;
  national: string;
  onChange: (next: { country: string; national: string }) => void;
}) {
  const iso = country || "MX";
  return (
    <TextInput
      className={classes.wrap}
      label={label}
      type="tel"
      inputMode="numeric"
      autoComplete="tel-national"
      value={national}
      leftSectionWidth={148}
      leftSection={
        <Select
          className={classes.country}
          aria-label={label}
          data={OPTIONS}
          searchable
          value={iso}
          allowDeselect={false}
          comboboxProps={{ withinPortal: true }}
          leftSection={<img src={flagUrl(iso)} width={18} height={14} alt="" />}
          leftSectionWidth={28}
          renderOption={({ option }) => (
            <Group gap={8} wrap="nowrap">
              <img src={flagUrl(option.value)} width={18} height={14} alt="" />
              <span>{option.label}</span>
            </Group>
          )}
          onChange={(value) => {
            if (!value) return;
            onChange({ country: value, national });
          }}
        />
      }
      onChange={(event) => {
        onChange({
          country: iso,
          national: event.currentTarget.value.replace(/\D/g, ""),
        });
      }}
    />
  );
}
