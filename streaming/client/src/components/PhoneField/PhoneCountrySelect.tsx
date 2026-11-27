import { Select, type SelectProps } from "@mantine/core";
import { useRef } from "react";

type CountryOption = { value: string; label: string };

type PhoneCountrySelectProps = Omit<
  SelectProps,
  "data" | "value" | "onChange" | "searchable" | "onSearchChange"
> & {
  data: CountryOption[];
  value: string | null;
  onChange: (value: string | null) => void;
};

/**
 * The country is one value. Backspace or Delete on the selected label clears
 * it entirely. A half-deleted label such as "Mexico (MX," is not a country.
 */
export function PhoneCountrySelect({
  data,
  value,
  onChange,
  onKeyDown,
  ...rest
}: PhoneCountrySelectProps) {
  const label =
    data.find((item) => item.value === value)?.label ?? "";
  const searchRef = useRef(label);
  const keyRef = useRef("");

  const clearCountry = () => {
    searchRef.current = "";
    onChange(null);
  };

  return (
    <Select
      {...rest}
      data={data}
      value={value}
      searchable
      clearable
      onChange={onChange}
      onKeyDown={(event) => {
        keyRef.current = event.key;
        onKeyDown?.(event);
        if (event.defaultPrevented || !value || !label) return;
        if (event.key !== "Backspace" && event.key !== "Delete") return;
        const node =
          event.target instanceof HTMLInputElement
            ? event.target
            : event.currentTarget;
        const text = node instanceof HTMLInputElement ? node.value : "";
        if (text === label || text === "") {
          event.preventDefault();
          clearCountry();
        }
      }}
      onSearchChange={(next) => {
        const key = keyRef.current;
        const previous = searchRef.current;
        searchRef.current = next;
        if (!value || !label || next === label) return;
        const deletingLabel =
          (key === "Backspace" || key === "Delete") &&
          previous === label &&
          next.length < label.length &&
          label.startsWith(next);
        if (deletingLabel || next === "") {
          clearCountry();
        }
      }}
    />
  );
}
