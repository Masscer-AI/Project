import { Input } from "@mantine/core";
import { PhoneInput } from "react-international-phone";
import "react-international-phone/style.css";
import { formatInternationalPhone } from "../../utils/countryDialCodes";
import classes from "./PhoneField.module.css";

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
  const iso = (country || "MX").toLowerCase();
  return (
    <Input.Wrapper label={label} className={classes.wrap}>
      <PhoneInput
        defaultCountry={iso}
        forceDialCode
        value={formatInternationalPhone(country || "MX", national)}
        inputClassName={classes.input}
        countrySelectorStyleProps={{ buttonClassName: classes.button }}
        onChange={(phone, meta) => {
          const dial = meta.country.dialCode;
          const digits = phone.replace(/\D/g, "");
          const local = digits.startsWith(dial) ? digits.slice(dial.length) : digits;
          onChange({
            country: meta.country.iso2.toUpperCase(),
            national: local,
          });
        }}
      />
    </Input.Wrapper>
  );
}
