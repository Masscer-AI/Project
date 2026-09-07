import React, { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Accordion,
  ActionIcon,
  Badge,
  Button,
  Group,
  Loader,
  NativeSelect,
  Select,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { IconPlus, IconTrash } from "@tabler/icons-react";
import { lookupPostalCode, TMyPldExpedient, updateMyPldExpedient } from "../../../modules/apiCalls";
import { countryNameSelectData, formatInternationalPhone, getDialCodeForIso, phoneCountrySelectData, splitInternationalPhone } from "../../../utils/countryDialCodes";
import { matchSubdivisionName, subdivisionSelectData } from "../../../utils/countrySubdivisions";

const COUNTRY_OPTIONS = countryNameSelectData();
const PHONE_COUNTRY_OPTIONS = phoneCountrySelectData();

function pickerValueFromIso(iso: string): Date | null {
  if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return null;
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return new Date(year, month - 1, day, 12, 0, 0);
}

function isoFromPicker(val: unknown): string {
  if (!val) return "";
  if (typeof val === "string" && /^\d{4}-\d{2}-\d{2}/.test(val)) {
    return val.slice(0, 10);
  }
  const date = val instanceof Date ? val : new Date(String(val));
  if (Number.isNaN(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function sanitizeLocalPhone(raw: string): string {
  return raw.replace(/\D/g, "");
}

function countrySelectValue(raw: string): string | null {
  const code = raw.trim().toUpperCase();
  return COUNTRY_OPTIONS.some((option) => option.value === code) ? code : null;
}

function sanitizePostalCode(country: string, raw: string): string {
  const iso = country.toUpperCase();
  if (iso === "CO") return raw.replace(/\D/g, "").slice(0, 6);
  if (iso === "MX" || iso === "US" || iso === "ES") {
    return raw.replace(/\D/g, "").slice(0, 5);
  }
  return raw.replace(/[^A-Za-z0-9\s-]/g, "").toUpperCase().slice(0, 12);
}

function postalCodeReady(country: string, code: string): boolean {
  const compact = code.replace(/\s/g, "");
  if (country === "MX" || country === "US" || country === "ES") {
    return /^\d{5}$/.test(compact);
  }
  if (country === "CO") return /^\d{6}$/.test(compact);
  if (country === "CA") return compact.length === 6;
  return compact.length >= 4;
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function joinedSurnames(
  surnames: unknown,
  paternal: unknown,
  maternal: unknown
): string {
  const direct = asString(surnames).trim();
  if (direct) return direct;
  return [asString(paternal), asString(maternal)]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(" ");
}

type ControllerRow = {
  name: string;
  rfc: string;
  ownership: string;
};

function emptyController(): ControllerRow {
  return { name: "", rfc: "", ownership: "" };
}

function loadControllers(meta: Record<string, unknown>): ControllerRow[] {
  const list = meta.controllers;
  if (Array.isArray(list) && list.length > 0) {
    const rows = list
      .filter((item) => item && typeof item === "object")
      .map((item) => {
        const row = item as Record<string, unknown>;
        return {
          name: asString(row.name),
          rfc: asString(row.rfc),
          ownership: asString(row.ownership_percentage),
        };
      });
    if (rows.length > 0) return rows;
  }
  const single = asRecord(meta.controller);
  if (asString(single.name)) {
    return [
      {
        name: asString(single.name),
        rfc: asString(single.rfc),
        ownership: asString(single.ownership_percentage),
      },
    ];
  }
  return [emptyController()];
}

type AddressFields = {
  street: string;
  exterior_number: string;
  interior_number: string;
  neighborhood: string;
  municipality: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
};

type FormState = {
  given_names: string;
  surnames: string;
  legal_name: string;
  date_of_birth: string;
  constitution_date: string;
  country_of_birth: string;
  nationality: string;
  curp: string;
  rfc: string;
  economic_activity: string;
  phone_iso: string;
  phone: string;
  email: string;
  id_document_type: string;
  id_issuing_authority: string;
  id_document_number: string;
  address: AddressFields;
  is_own_controller: boolean;
  controllers: ControllerRow[];
  rep_given_names: string;
  rep_surnames: string;
  rep_date_of_birth: string;
  rep_rfc: string;
  rep_curp: string;
  rep_id_document_type: string;
  rep_id_issuing_authority: string;
  rep_id_document_number: string;
};

function fromMetadata(row: TMyPldExpedient): FormState {
  const meta = asRecord(row.metadata);
  const address = asRecord(meta.address);
  const identification = asRecord(meta.identification);
  const representative = asRecord(meta.representative);
  const repId = asRecord(representative.identification);
  const given = asString(meta.given_names);
  const parsedPhone = splitInternationalPhone(asString(meta.phone));
  return {
    given_names: given || asString(meta.name),
    surnames: joinedSurnames(
      meta.surnames,
      meta.paternal_surname,
      meta.maternal_surname
    ),
    legal_name: asString(meta.legal_name) || row.name,
    date_of_birth: asString(meta.date_of_birth),
    constitution_date: asString(meta.constitution_date),
    country_of_birth: asString(meta.country_of_birth),
    nationality: asString(meta.nationality) || "MX",
    curp: asString(meta.curp),
    rfc: asString(meta.rfc),
    economic_activity: asString(meta.economic_activity),
    phone_iso: parsedPhone.iso,
    phone: parsedPhone.local,
    email: asString(meta.email) || asString(row.email),
    id_document_type: asString(identification.document_type),
    id_issuing_authority: asString(identification.issuing_authority),
    id_document_number: asString(identification.document_number),
    address: {
      street: asString(address.street),
      exterior_number: asString(address.exterior_number),
      interior_number: asString(address.interior_number),
      neighborhood: asString(address.neighborhood),
      municipality: asString(address.municipality),
      city: asString(address.city),
      state: asString(address.state),
      postal_code: asString(address.postal_code),
      country: asString(address.country) || "MX",
    },
    is_own_controller: meta.is_own_controller !== false,
    controllers: loadControllers(meta),
    rep_given_names: asString(representative.given_names),
    rep_surnames: joinedSurnames(
      representative.surnames,
      representative.paternal_surname,
      representative.maternal_surname
    ),
    rep_date_of_birth: asString(representative.date_of_birth),
    rep_rfc: asString(representative.rfc),
    rep_curp: asString(representative.curp),
    rep_id_document_type: asString(repId.document_type),
    rep_id_issuing_authority: asString(repId.issuing_authority),
    rep_id_document_number: asString(repId.document_number),
  };
}

function filled(value: string): boolean {
  return Boolean(value.trim());
}

function addressSectionComplete(address: AddressFields): boolean {
  return [
    address.country,
    address.postal_code,
    address.state,
    address.municipality,
    address.city,
    address.neighborhood,
    address.street,
    address.exterior_number,
  ].every(filled);
}

function showIssuingAuthority(documentType: string): boolean {
  return documentType === "other" || documentType === "professional_license";
}

function SectionStatus({
  done,
  t,
}: {
  done: boolean;
  t: (key: string) => string;
}) {
  return (
    <Badge size="xs" variant="light" color={done ? "teal" : "violet"}>
      {done ? t("compliance-intake-section-done") : t("compliance-intake-section-pending")}
    </Badge>
  );
}

function compactAddress(address: AddressFields): AddressFields | undefined {
  const hasValue = Object.values(address).some((value) => value.trim());
  return hasValue ? address : undefined;
}

function identificationPayload(type: string, authority: string, number: string) {
  if (!type.trim() && !authority.trim() && !number.trim()) return undefined;
  return {
    document_type: type.trim() || null,
    issuing_authority: authority.trim() || null,
    document_number: number.trim() || null,
  };
}

function namedControllers(form: FormState) {
  return form.controllers
    .filter((row) => row.name.trim())
    .map((row) => ({
      name: row.name.trim(),
      rfc: row.rfc.trim() || null,
      ownership_percentage: row.ownership.trim() || null,
    }));
}

function metadataFromForm(form: FormState, isMoral: boolean): Record<string, unknown> {
  const phoneDigits = form.phone.replace(/\D/g, "");
  const phone =
    phoneDigits.length >= 7
      ? formatInternationalPhone(form.phone_iso || "MX", form.phone) || null
      : null;
  const controllers = namedControllers(form);
  if (isMoral) {
    return {
      schema_version: 2,
      legal_name: form.legal_name.trim() || null,
      constitution_date: form.constitution_date.trim() || null,
      nationality: form.nationality.trim() || null,
      rfc: form.rfc.trim() || null,
      economic_activity: form.economic_activity.trim() || null,
      phone,
      email: form.email.trim() || null,
      address: compactAddress(form.address),
      representative: {
        given_names: form.rep_given_names.trim() || null,
        surnames: form.rep_surnames.trim() || null,
        date_of_birth: form.rep_date_of_birth.trim() || null,
        rfc: form.rep_rfc.trim() || null,
        curp: form.rep_curp.trim() || null,
        identification: identificationPayload(
          form.rep_id_document_type,
          form.rep_id_issuing_authority,
          form.rep_id_document_number
        ),
      },
      controllers,
    };
  }
  return {
    schema_version: 2,
    given_names: form.given_names.trim() || null,
    surnames: form.surnames.trim() || null,
    date_of_birth: form.date_of_birth.trim() || null,
    country_of_birth: form.country_of_birth.trim() || null,
    nationality: form.nationality.trim() || null,
    curp: form.curp.trim() || null,
    rfc: form.rfc.trim() || null,
    economic_activity: form.economic_activity.trim() || null,
    phone,
    email: form.email.trim() || null,
    address: compactAddress(form.address),
    identification: identificationPayload(
      form.id_document_type,
      form.id_issuing_authority,
      form.id_document_number
    ),
    is_own_controller: form.is_own_controller,
    controller: form.is_own_controller ? null : controllers[0] || null,
    controllers: form.is_own_controller ? [] : controllers,
  };
}

const AUTOSAVE_MS = 700;

export function PldIntakeForm({
  row,
  onSaved,
}: {
  row: TMyPldExpedient;
  onSaved: (next: TMyPldExpedient) => void;
}) {
  const { t } = useTranslation();
  const isMoral = row.person_type === "persona_moral";
  const [form, setForm] = useState<FormState>(() => fromMetadata(row));
  const [sync, setSync] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [openedSection, setOpenedSection] = useState<string | null>("entity");
  const [neighborhoodOptions, setNeighborhoodOptions] = useState<string[]>([]);
  const [postalLookupLoading, setPostalLookupLoading] = useState(false);
  const dirty = useRef(false);
  const formRef = useRef(form);
  const lastSaved = useRef(JSON.stringify(metadataFromForm(fromMetadata(row), isMoral)));
  const inFlight = useRef(false);
  const pendingSave = useRef(false);
  const saveTimer = useRef<number | undefined>(undefined);
  const onSavedRef = useRef(onSaved);
  formRef.current = form;
  onSavedRef.current = onSaved;

  const idOptions = useMemo(
    () => [
      { value: "", label: t("compliance-intake-id-placeholder") },
      { value: "ine", label: t("compliance-intake-id-ine") },
      { value: "passport", label: t("compliance-intake-id-passport") },
      { value: "professional_license", label: t("compliance-intake-id-license") },
      { value: "other", label: t("compliance-intake-id-other") },
    ],
    [t]
  );

  const addressCountryIso =
    countrySelectValue(form.address.country) || "MX";
  const stateOptions = subdivisionSelectData(
    addressCountryIso,
    form.address.state
  );

  useEffect(() => {
    const postalCode = form.address.postal_code.trim();
    if (!postalCodeReady(addressCountryIso, postalCode)) {
      setPostalLookupLoading(false);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setPostalLookupLoading(true);
      lookupPostalCode(addressCountryIso, postalCode)
        .then((result) => {
          if (cancelled || !result?.found) return;
          const neighborhoods = result.neighborhoods || [];
          setNeighborhoodOptions(neighborhoods);
          setForm((prev) => {
            const nextNeighborhood =
              neighborhoods.length === 1
                ? neighborhoods[0]
                : neighborhoods.includes(prev.address.neighborhood)
                  ? prev.address.neighborhood
                  : prev.address.neighborhood;
            return {
              ...prev,
              address: {
                ...prev.address,
                state:
                  matchSubdivisionName(addressCountryIso, result.state || "") ||
                  prev.address.state,
                municipality:
                  result.municipality || prev.address.municipality,
                city: result.city || prev.address.city,
                neighborhood: nextNeighborhood,
              },
            };
          });
        })
        .catch(() => undefined)
        .finally(() => {
          if (!cancelled) setPostalLookupLoading(false);
        });
    }, 400);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [addressCountryIso, form.address.postal_code]);

  const setField = (key: keyof FormState, value: string | boolean) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const setAddress = (key: keyof AddressFields, value: string) => {
    setForm((prev) => ({
      ...prev,
      address: { ...prev.address, [key]: value },
    }));
  };

  const setAddressCountry = (iso: string) => {
    setForm((prev) => {
      const nextIso = iso || "MX";
      const options = subdivisionSelectData(nextIso, prev.address.state);
      const stateStillValid = Boolean(
        options?.some((option) => option.value === prev.address.state)
      );
      return {
        ...prev,
        address: {
          ...prev.address,
          country: nextIso,
          state: stateStillValid ? prev.address.state : "",
        },
      };
    });
    setNeighborhoodOptions([]);
  };

  const setController = (
    index: number,
    key: keyof ControllerRow,
    value: string
  ) => {
    setForm((prev) => ({
      ...prev,
      controllers: prev.controllers.map((row, i) =>
        i === index ? { ...row, [key]: value } : row
      ),
    }));
  };

  const addController = () => {
    setForm((prev) => ({
      ...prev,
      controllers: [...prev.controllers, emptyController()],
    }));
  };

  const removeController = (index: number) => {
    setForm((prev) => {
      const next = prev.controllers.filter((_, i) => i !== index);
      return {
        ...prev,
        controllers: next.length > 0 ? next : [emptyController()],
      };
    });
  };

  const isMexican = (form.nationality || "MX") === "MX";
  const entityDone = isMoral
    ? filled(form.legal_name) &&
      filled(form.constitution_date) &&
      filled(form.nationality) &&
      filled(form.rfc) &&
      filled(form.economic_activity)
    : filled(form.given_names) &&
      filled(form.surnames) &&
      filled(form.date_of_birth) &&
      filled(form.country_of_birth) &&
      filled(form.nationality) &&
      filled(form.economic_activity) &&
      (!isMexican || (filled(form.rfc) && filled(form.curp)));
  const addressDone = addressSectionComplete(form.address);
  const idDone =
    filled(form.id_document_type) && filled(form.id_document_number);
  const representativeDone =
    filled(form.rep_given_names) &&
    filled(form.rep_surnames) &&
    filled(form.rep_id_document_type) &&
    filled(form.rep_id_document_number);
  const controllerDone =
    (!isMoral && form.is_own_controller) ||
    form.controllers.some((item) => filled(item.name));
  const sectionOrder = isMoral
    ? ["entity", "address", "representative", "controller"]
    : ["entity", "address", "identification", "controller"];
  const goNextSection = () => {
    const index = sectionOrder.indexOf(openedSection || "entity");
    const next = sectionOrder[index + 1];
    if (next) setOpenedSection(next);
  };

  const flushSave = async () => {
    if (!dirty.current) return;
    if (inFlight.current) {
      pendingSave.current = true;
      return;
    }
    inFlight.current = true;
    pendingSave.current = false;
    setSync("saving");
    try {
      const payload = metadataFromForm(formRef.current, isMoral);
      const saved = await updateMyPldExpedient(row.id, payload);
      onSavedRef.current(saved);
      lastSaved.current = JSON.stringify(payload);
      setSync("saved");
    } catch {
      setSync("error");
    } finally {
      inFlight.current = false;
      if (pendingSave.current) {
        pendingSave.current = false;
        void flushSave();
      }
    }
  };

  useEffect(() => {
    const next = JSON.stringify(metadataFromForm(form, isMoral));
    if (next === lastSaved.current) return;
    dirty.current = true;
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => {
      void flushSave();
    }, AUTOSAVE_MS);
    return () => window.clearTimeout(saveTimer.current);
  }, [form]);

  useEffect(() => {
    const flushNow = () => {
      window.clearTimeout(saveTimer.current);
      void flushSave();
    };
    const onHide = () => {
      if (document.visibilityState === "hidden") flushNow();
    };
    window.addEventListener("pagehide", flushNow);
    document.addEventListener("visibilitychange", onHide);
    return () => {
      window.removeEventListener("pagehide", flushNow);
      document.removeEventListener("visibilitychange", onHide);
      window.clearTimeout(saveTimer.current);
    };
  }, [row.id]);

  return (
    <Stack gap="sm" mt="md">
      <Group justify="space-between" align="flex-start" gap="sm">
        <Title order={5}>
          {isMoral
            ? t("compliance-intake-moral-section")
            : t("compliance-intake-fisica-section")}
        </Title>
        <Text
          size="xs"
          c={sync === "error" ? "red" : "dimmed"}
          style={sync === "error" ? { cursor: "pointer" } : undefined}
          onClick={
            sync === "error"
              ? () => {
                  dirty.current = true;
                  void flushSave();
                }
              : undefined
          }
        >
          {sync === "saving"
            ? t("compliance-intake-sync-saving")
            : sync === "saved"
              ? t("compliance-intake-sync-saved")
              : sync === "error"
                ? t("compliance-intake-sync-error")
                : null}
        </Text>
      </Group>
      <Text size="sm" c="dimmed">
        {row.expedient?.status && row.expedient.status !== "data_collection"
          ? t("compliance-intake-data-saved-hint")
          : t("compliance-intake-documents-later")}
      </Text>
      <Text size="sm" c="dimmed">
        {t("compliance-intake-required-legend")}
      </Text>

      <Accordion
        variant="separated"
        radius="md"
        value={openedSection}
        onChange={setOpenedSection}
      >
        <Accordion.Item value="entity">
          <Accordion.Control>
            <Group gap="xs" wrap="nowrap" justify="space-between" pr="sm">
              <Text fw={500}>
                {isMoral
                  ? t("compliance-intake-section-entity-moral")
                  : t("compliance-intake-section-entity-fisica")}
              </Text>
              <SectionStatus done={entityDone} t={t} />
            </Group>
          </Accordion.Control>
          <Accordion.Panel>
            <Stack gap="sm">
      {isMoral ? (
        <TextInput
          label={t("compliance-intake-legal-name")}
          required
          value={form.legal_name}
          onChange={(e) => setField("legal_name", e.currentTarget.value)}
        />
      ) : (
        <Group grow>
          <TextInput
            label={t("compliance-intake-given-names")}
            required
            value={form.given_names}
            onChange={(e) => setField("given_names", e.currentTarget.value)}
          />
          <TextInput
            label={t("compliance-intake-surnames")}
            required
            value={form.surnames}
            onChange={(e) => setField("surnames", e.currentTarget.value)}
          />
        </Group>
      )}

      <Group grow>
        <DatePickerInput
          label={
            isMoral
              ? t("compliance-intake-constitution-date")
              : t("compliance-intake-date-of-birth")
          }
          required
          valueFormat="YYYY-MM-DD"
          clearable
          maxDate={new Date()}
          value={pickerValueFromIso(
            isMoral ? form.constitution_date : form.date_of_birth
          )}
          onChange={(val) => {
            const iso = isoFromPicker(val);
            setField(isMoral ? "constitution_date" : "date_of_birth", iso);
          }}
        />
        {!isMoral && (
          <Select
            label={t("compliance-intake-country-of-birth")}
            required
            data={COUNTRY_OPTIONS}
            searchable
            clearable
            nothingFoundMessage={t("compliance-intake-country-not-found")}
            comboboxProps={{ withinPortal: true }}
            value={countrySelectValue(form.country_of_birth)}
            onChange={(val) => setField("country_of_birth", val || "")}
          />
        )}
        <Select
          label={t("compliance-intake-nationality")}
          required
          data={COUNTRY_OPTIONS}
          searchable
          nothingFoundMessage={t("compliance-intake-country-not-found")}
          comboboxProps={{ withinPortal: true }}
          value={countrySelectValue(form.nationality) || "MX"}
          onChange={(val) => setField("nationality", val || "MX")}
        />
      </Group>

      <Group grow>
        <TextInput
          label={
            isMoral
              ? t("compliance-intake-rfc-entity")
              : t("compliance-intake-rfc-person")
          }
          required={isMoral || isMexican}
          value={form.rfc}
          onChange={(e) => setField("rfc", e.currentTarget.value)}
        />
        {!isMoral && (
          <TextInput
            label="CURP"
            required={isMexican}
            value={form.curp}
            onChange={(e) => setField("curp", e.currentTarget.value)}
          />
        )}
        <TextInput
          label={t("compliance-intake-activity")}
          description={
            isMoral
              ? t("compliance-intake-activity-hint-moral")
              : t("compliance-intake-activity-hint-fisica")
          }
          required
          value={form.economic_activity}
          onChange={(e) => setField("economic_activity", e.currentTarget.value)}
        />
      </Group>

      <Group grow align="flex-end">
        <Select
          label={t("phone-country")}
          placeholder={t("phone-country-placeholder")}
          data={PHONE_COUNTRY_OPTIONS}
          searchable
          nothingFoundMessage={t("phone-country-not-found")}
          comboboxProps={{ withinPortal: true }}
          value={form.phone_iso || "MX"}
          onChange={(val) => setField("phone_iso", val || "MX")}
        />
        <TextInput
          label={t("compliance-intake-phone")}
          type="tel"
          inputMode="numeric"
          autoComplete="tel-national"
          placeholder="5512345678"
          description={`+${getDialCodeForIso(form.phone_iso || "MX")}`}
          value={form.phone}
          onChange={(e) => {
            const val = sanitizeLocalPhone(e.currentTarget.value);
            setField("phone", val);
          }}
        />
        <TextInput
          label={t("email")}
          type="email"
          autoComplete="email"
          value={form.email}
          onChange={(e) => setField("email", e.currentTarget.value)}
        />
      </Group>
              <Button variant="default" size="xs" onClick={goNextSection} w="fit-content">
                {t("compliance-intake-next-section")}
              </Button>
            </Stack>
          </Accordion.Panel>
        </Accordion.Item>

        <Accordion.Item value="address">
          <Accordion.Control>
            <Group gap="xs" wrap="nowrap" justify="space-between" pr="sm">
              <Text fw={500}>{t("compliance-intake-address")}</Text>
              <SectionStatus done={addressDone} t={t} />
            </Group>
          </Accordion.Control>
          <Accordion.Panel>
            <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {t("compliance-intake-postal-lookup-hint")}
      </Text>
      <Group grow>
        <Select
          label={t("compliance-intake-country")}
          required
          data={COUNTRY_OPTIONS}
          searchable
          nothingFoundMessage={t("compliance-intake-country-not-found")}
          comboboxProps={{ withinPortal: true }}
          value={addressCountryIso}
          onChange={(val) => setAddressCountry(val || "MX")}
        />
        <TextInput
          label={t("compliance-intake-postal-code")}
          required
          inputMode={
            addressCountryIso === "MX" ||
            addressCountryIso === "US" ||
            addressCountryIso === "ES" ||
            addressCountryIso === "CO"
              ? "numeric"
              : "text"
          }
          value={form.address.postal_code}
          rightSection={postalLookupLoading ? <Loader size="xs" /> : null}
          onChange={(e) => {
            const val = sanitizePostalCode(
              addressCountryIso,
              e.currentTarget.value
            );
            setAddress("postal_code", val);
          }}
        />
      </Group>
      <Group grow>
        {stateOptions ? (
          <Select
            label={t("compliance-intake-state")}
            required
            placeholder={t("compliance-intake-state-placeholder")}
            data={stateOptions}
            searchable
            clearable
            nothingFoundMessage={t("compliance-intake-state-not-found")}
            comboboxProps={{ withinPortal: true }}
            value={form.address.state || null}
            onChange={(val) => setAddress("state", val || "")}
          />
        ) : (
          <TextInput
            label={t("compliance-intake-state")}
            required
            value={form.address.state}
            onChange={(e) => setAddress("state", e.currentTarget.value)}
          />
        )}
        <TextInput
          label={t("compliance-intake-municipality")}
          required
          value={form.address.municipality}
          onChange={(e) => setAddress("municipality", e.currentTarget.value)}
        />
        <TextInput
          label={t("compliance-intake-city")}
          required
          value={form.address.city}
          onChange={(e) => setAddress("city", e.currentTarget.value)}
        />
      </Group>
      {neighborhoodOptions.length > 1 ? (
        <Select
          label={t("compliance-intake-neighborhood")}
          required
          placeholder={t("compliance-intake-neighborhood-placeholder")}
          data={neighborhoodOptions.map((name) => ({
            value: name,
            label: name,
          }))}
          searchable
          comboboxProps={{ withinPortal: true }}
          value={form.address.neighborhood || null}
          onChange={(val) => setAddress("neighborhood", val || "")}
        />
      ) : (
        <TextInput
          label={t("compliance-intake-neighborhood")}
          required
          value={form.address.neighborhood}
          onChange={(e) => setAddress("neighborhood", e.currentTarget.value)}
        />
      )}
      <TextInput
        label={t("compliance-intake-street")}
        required
        value={form.address.street}
        onChange={(e) => setAddress("street", e.currentTarget.value)}
      />
      <Group grow>
        <TextInput
          label={t("compliance-intake-ext-number")}
          required
          value={form.address.exterior_number}
          onChange={(e) => setAddress("exterior_number", e.currentTarget.value)}
        />
        <TextInput
          label={t("compliance-intake-int-number")}
          value={form.address.interior_number}
          onChange={(e) => setAddress("interior_number", e.currentTarget.value)}
        />
      </Group>
              <Button variant="default" size="xs" onClick={goNextSection} w="fit-content">
                {t("compliance-intake-next-section")}
              </Button>
            </Stack>
          </Accordion.Panel>
        </Accordion.Item>

      {!isMoral && (
        <Accordion.Item value="identification">
          <Accordion.Control>
            <Group gap="xs" wrap="nowrap" justify="space-between" pr="sm">
              <Text fw={500}>{t("compliance-intake-identification")}</Text>
              <SectionStatus done={idDone} t={t} />
            </Group>
          </Accordion.Control>
          <Accordion.Panel>
            <Stack gap="sm">
          <Group grow>
            <NativeSelect
              label={t("compliance-intake-id-type")}
              required
              data={idOptions}
              value={form.id_document_type}
              onChange={(e) => setField("id_document_type", e.currentTarget.value)}
            />
            <TextInput
              label={t("compliance-intake-id-number")}
              required
              value={form.id_document_number}
              onChange={(e) => setField("id_document_number", e.currentTarget.value)}
            />
          </Group>
          {showIssuingAuthority(form.id_document_type) && (
            <TextInput
              label={t("compliance-intake-id-authority")}
              description={t("compliance-intake-id-authority-hint")}
              value={form.id_issuing_authority}
              onChange={(e) => setField("id_issuing_authority", e.currentTarget.value)}
            />
          )}
              <Button variant="default" size="xs" onClick={goNextSection} w="fit-content">
                {t("compliance-intake-next-section")}
              </Button>
            </Stack>
          </Accordion.Panel>
        </Accordion.Item>
      )}

      {isMoral && (
        <Accordion.Item value="representative">
          <Accordion.Control>
            <Group gap="xs" wrap="nowrap" justify="space-between" pr="sm">
              <Text fw={500}>{t("compliance-intake-representative")}</Text>
              <SectionStatus done={representativeDone} t={t} />
            </Group>
          </Accordion.Control>
          <Accordion.Panel>
            <Stack gap="sm">
          <Text size="sm" c="dimmed">
            {t("compliance-intake-representative-hint")}
          </Text>
          <Group grow>
            <TextInput
              label={t("compliance-intake-given-names")}
              required
              value={form.rep_given_names}
              onChange={(e) => setField("rep_given_names", e.currentTarget.value)}
            />
            <TextInput
              label={t("compliance-intake-surnames")}
              required
              value={form.rep_surnames}
              onChange={(e) => setField("rep_surnames", e.currentTarget.value)}
            />
          </Group>
          <Group grow>
            <DatePickerInput
              label={t("compliance-intake-date-of-birth")}
              valueFormat="YYYY-MM-DD"
              clearable
              maxDate={new Date()}
              value={pickerValueFromIso(form.rep_date_of_birth)}
              onChange={(val) => setField("rep_date_of_birth", isoFromPicker(val))}
            />
            <TextInput
              label={t("compliance-intake-rfc-representative")}
              value={form.rep_rfc}
              onChange={(e) => setField("rep_rfc", e.currentTarget.value)}
            />
            <TextInput
              label={t("compliance-intake-curp-representative")}
              value={form.rep_curp}
              onChange={(e) => setField("rep_curp", e.currentTarget.value)}
            />
          </Group>
          <Group grow>
            <NativeSelect
              label={t("compliance-intake-id-type")}
              required
              data={idOptions}
              value={form.rep_id_document_type}
              onChange={(e) =>
                setField("rep_id_document_type", e.currentTarget.value)
              }
            />
            <TextInput
              label={t("compliance-intake-id-number")}
              required
              value={form.rep_id_document_number}
              onChange={(e) =>
                setField("rep_id_document_number", e.currentTarget.value)
              }
            />
          </Group>
          {showIssuingAuthority(form.rep_id_document_type) && (
            <TextInput
              label={t("compliance-intake-id-authority")}
              description={t("compliance-intake-id-authority-hint")}
              value={form.rep_id_issuing_authority}
              onChange={(e) =>
                setField("rep_id_issuing_authority", e.currentTarget.value)
              }
            />
          )}
              <Button variant="default" size="xs" onClick={goNextSection} w="fit-content">
                {t("compliance-intake-next-section")}
              </Button>
            </Stack>
          </Accordion.Panel>
        </Accordion.Item>
      )}

        <Accordion.Item value="controller">
          <Accordion.Control>
            <Group gap="xs" wrap="nowrap" justify="space-between" pr="sm">
              <Text fw={500}>{t("compliance-intake-controller")}</Text>
              <SectionStatus done={controllerDone} t={t} />
            </Group>
          </Accordion.Control>
          <Accordion.Panel>
            <Stack gap="sm">
              <Text size="sm" c="dimmed">
                {isMoral
                  ? t("compliance-intake-controller-hint-moral")
                  : t("compliance-intake-controller-hint-fisica")}
              </Text>
              {!isMoral && (
                <Switch
                  label={t("compliance-intake-own-controller")}
                  checked={form.is_own_controller}
                  onChange={(e) =>
                    setField("is_own_controller", e.currentTarget.checked)
                  }
                />
              )}
              {(isMoral || !form.is_own_controller) && (
                <Stack gap="sm">
                  {form.controllers.map((row, index) => (
                    <Group key={index} align="flex-end" wrap="nowrap" gap="xs">
                      <TextInput
                        style={{ flex: 1 }}
                        label={
                          index === 0
                            ? t("compliance-intake-controller-name")
                            : undefined
                        }
                        required={index === 0}
                        value={row.name}
                        onChange={(e) =>
                          setController(index, "name", e.currentTarget.value)
                        }
                      />
                      <TextInput
                        style={{ flex: 1 }}
                        label={
                          index === 0
                            ? t("compliance-intake-rfc-controller")
                            : undefined
                        }
                        value={row.rfc}
                        onChange={(e) =>
                          setController(index, "rfc", e.currentTarget.value)
                        }
                      />
                      <TextInput
                        style={{ flex: 1 }}
                        label={
                          index === 0
                            ? t("compliance-intake-ownership")
                            : undefined
                        }
                        value={row.ownership}
                        onChange={(e) =>
                          setController(index, "ownership", e.currentTarget.value)
                        }
                      />
                      <ActionIcon
                        variant="subtle"
                        color="gray"
                        mb={4}
                        aria-label={t("compliance-intake-remove-controller")}
                        onClick={() => removeController(index)}
                        disabled={form.controllers.length === 1}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  ))}
                  <Button
                    variant="default"
                    size="xs"
                    leftSection={<IconPlus size={14} />}
                    onClick={addController}
                    w="fit-content"
                  >
                    {t("compliance-intake-add-controller")}
                  </Button>
                </Stack>
              )}
            </Stack>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </Stack>
  );
}
