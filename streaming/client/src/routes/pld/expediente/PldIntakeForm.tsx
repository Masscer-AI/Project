import React, { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Button,
  Divider,
  Group,
  NativeSelect,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconPlus, IconTrash } from "@tabler/icons-react";
import { TMyPldExpedient, updateMyPldExpedient } from "../../../modules/apiCalls";

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
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
  paternal_surname: string;
  maternal_surname: string;
  legal_name: string;
  date_of_birth: string;
  constitution_date: string;
  country_of_birth: string;
  nationality: string;
  curp: string;
  rfc: string;
  economic_activity: string;
  phone: string;
  email: string;
  id_document_type: string;
  id_issuing_authority: string;
  id_document_number: string;
  address: AddressFields;
  is_own_controller: boolean;
  controllers: ControllerRow[];
  rep_given_names: string;
  rep_paternal_surname: string;
  rep_maternal_surname: string;
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
  return {
    given_names: given || asString(meta.name),
    paternal_surname: asString(meta.paternal_surname),
    maternal_surname: asString(meta.maternal_surname),
    legal_name: asString(meta.legal_name) || row.name,
    date_of_birth: asString(meta.date_of_birth),
    constitution_date: asString(meta.constitution_date),
    country_of_birth: asString(meta.country_of_birth),
    nationality: asString(meta.nationality) || "MX",
    curp: asString(meta.curp),
    rfc: asString(meta.rfc),
    economic_activity: asString(meta.economic_activity),
    phone: asString(meta.phone),
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
    rep_paternal_surname: asString(representative.paternal_surname),
    rep_maternal_surname: asString(representative.maternal_surname),
    rep_date_of_birth: asString(representative.date_of_birth),
    rep_rfc: asString(representative.rfc),
    rep_curp: asString(representative.curp),
    rep_id_document_type: asString(repId.document_type),
    rep_id_issuing_authority: asString(repId.issuing_authority),
    rep_id_document_number: asString(repId.document_number),
  };
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
  const [saving, setSaving] = useState(false);

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

  const setField = (key: keyof FormState, value: string | boolean) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const setAddress = (key: keyof AddressFields, value: string) => {
    setForm((prev) => ({
      ...prev,
      address: { ...prev.address, [key]: value },
    }));
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

  const namedControllers = () =>
    form.controllers
      .filter((row) => row.name.trim())
      .map((row) => ({
        name: row.name.trim(),
        rfc: row.rfc.trim() || null,
        ownership_percentage: row.ownership.trim() || null,
      }));

  const handleSave = async () => {
    if (isMoral && !form.legal_name.trim()) {
      toast.error(t("compliance-intake-legal-name-required"));
      return;
    }
    if (!isMoral && !form.given_names.trim()) {
      toast.error(t("compliance-intake-given-names-required"));
      return;
    }
    const controllers = namedControllers();
    if (isMoral && controllers.length === 0) {
      toast.error(t("compliance-intake-controller-name-required"));
      return;
    }
    if (!isMoral && !form.is_own_controller && controllers.length === 0) {
      toast.error(t("compliance-intake-controller-name-required"));
      return;
    }

    const metadata: Record<string, unknown> = isMoral
      ? {
          schema_version: 2,
          legal_name: form.legal_name.trim(),
          constitution_date: form.constitution_date.trim() || null,
          nationality: form.nationality.trim() || null,
          rfc: form.rfc.trim() || null,
          economic_activity: form.economic_activity.trim() || null,
          phone: form.phone.trim() || null,
          email: form.email.trim() || null,
          address: compactAddress(form.address),
          representative: {
            given_names: form.rep_given_names.trim() || null,
            paternal_surname: form.rep_paternal_surname.trim() || null,
            maternal_surname: form.rep_maternal_surname.trim() || null,
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
        }
      : {
          schema_version: 2,
          given_names: form.given_names.trim(),
          paternal_surname: form.paternal_surname.trim() || null,
          maternal_surname: form.maternal_surname.trim() || null,
          date_of_birth: form.date_of_birth.trim() || null,
          country_of_birth: form.country_of_birth.trim() || null,
          nationality: form.nationality.trim() || null,
          curp: form.curp.trim() || null,
          rfc: form.rfc.trim() || null,
          economic_activity: form.economic_activity.trim() || null,
          phone: form.phone.trim() || null,
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

    setSaving(true);
    try {
      const saved = await updateMyPldExpedient(row.id, metadata);
      onSaved(saved);
      toast.success(t("compliance-intake-saved"));
    } catch {
      toast.error(t("compliance-intake-save-error"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Stack gap="sm" mt="md">
      <Title order={5}>
        {isMoral
          ? t("compliance-intake-moral-section")
          : t("compliance-intake-fisica-section")}
      </Title>
      <Text size="sm" c="dimmed">
        {t("compliance-intake-documents-later")}
      </Text>

      {isMoral ? (
        <TextInput
          label={t("compliance-intake-legal-name")}
          value={form.legal_name}
          onChange={(e) => setField("legal_name", e.currentTarget.value)}
        />
      ) : (
        <Group grow>
          <TextInput
            label={t("compliance-intake-given-names")}
            value={form.given_names}
            onChange={(e) => setField("given_names", e.currentTarget.value)}
          />
          <TextInput
            label={t("compliance-intake-paternal-surname")}
            value={form.paternal_surname}
            onChange={(e) => setField("paternal_surname", e.currentTarget.value)}
          />
          <TextInput
            label={t("compliance-intake-maternal-surname")}
            value={form.maternal_surname}
            onChange={(e) => setField("maternal_surname", e.currentTarget.value)}
          />
        </Group>
      )}

      <Group grow>
        <TextInput
          label={
            isMoral
              ? t("compliance-intake-constitution-date")
              : t("compliance-intake-date-of-birth")
          }
          placeholder="YYYY-MM-DD"
          value={isMoral ? form.constitution_date : form.date_of_birth}
          onChange={(e) => {
            const val = e.currentTarget.value;
            setField(isMoral ? "constitution_date" : "date_of_birth", val);
          }}
        />
        {!isMoral && (
          <TextInput
            label={t("compliance-intake-country-of-birth")}
            value={form.country_of_birth}
            onChange={(e) => setField("country_of_birth", e.currentTarget.value)}
          />
        )}
        <TextInput
          label={t("compliance-intake-nationality")}
          value={form.nationality}
          onChange={(e) => setField("nationality", e.currentTarget.value)}
        />
      </Group>

      <Group grow>
        <TextInput
          label="RFC"
          value={form.rfc}
          onChange={(e) => setField("rfc", e.currentTarget.value)}
        />
        {!isMoral && (
          <TextInput
            label="CURP"
            value={form.curp}
            onChange={(e) => setField("curp", e.currentTarget.value)}
          />
        )}
        <TextInput
          label={t("compliance-intake-activity")}
          value={form.economic_activity}
          onChange={(e) => setField("economic_activity", e.currentTarget.value)}
        />
      </Group>

      <Group grow>
        <TextInput
          label={t("compliance-intake-phone")}
          value={form.phone}
          onChange={(e) => setField("phone", e.currentTarget.value)}
        />
        <TextInput
          label={t("email")}
          value={form.email}
          onChange={(e) => setField("email", e.currentTarget.value)}
        />
      </Group>

      <Divider label={t("compliance-intake-address")} labelPosition="left" />
      <TextInput
        label={t("compliance-intake-street")}
        value={form.address.street}
        onChange={(e) => setAddress("street", e.currentTarget.value)}
      />
      <Group grow>
        <TextInput
          label={t("compliance-intake-ext-number")}
          value={form.address.exterior_number}
          onChange={(e) => setAddress("exterior_number", e.currentTarget.value)}
        />
        <TextInput
          label={t("compliance-intake-int-number")}
          value={form.address.interior_number}
          onChange={(e) => setAddress("interior_number", e.currentTarget.value)}
        />
        <TextInput
          label={t("compliance-intake-neighborhood")}
          value={form.address.neighborhood}
          onChange={(e) => setAddress("neighborhood", e.currentTarget.value)}
        />
      </Group>
      <Group grow>
        <TextInput
          label={t("compliance-intake-municipality")}
          value={form.address.municipality}
          onChange={(e) => setAddress("municipality", e.currentTarget.value)}
        />
        <TextInput
          label={t("compliance-intake-city")}
          value={form.address.city}
          onChange={(e) => setAddress("city", e.currentTarget.value)}
        />
        <TextInput
          label={t("compliance-intake-state")}
          value={form.address.state}
          onChange={(e) => setAddress("state", e.currentTarget.value)}
        />
      </Group>
      <Group grow>
        <TextInput
          label={t("compliance-intake-postal-code")}
          value={form.address.postal_code}
          onChange={(e) => setAddress("postal_code", e.currentTarget.value)}
        />
        <TextInput
          label={t("compliance-intake-country")}
          value={form.address.country}
          onChange={(e) => setAddress("country", e.currentTarget.value)}
        />
      </Group>

      {!isMoral && (
        <>
          <Divider label={t("compliance-intake-identification")} labelPosition="left" />
          <Group grow>
            <NativeSelect
              label={t("compliance-intake-id-type")}
              data={idOptions}
              value={form.id_document_type}
              onChange={(e) => setField("id_document_type", e.currentTarget.value)}
            />
            <TextInput
              label={t("compliance-intake-id-authority")}
              value={form.id_issuing_authority}
              onChange={(e) => setField("id_issuing_authority", e.currentTarget.value)}
            />
            <TextInput
              label={t("compliance-intake-id-number")}
              value={form.id_document_number}
              onChange={(e) => setField("id_document_number", e.currentTarget.value)}
            />
          </Group>
        </>
      )}

      {isMoral && (
        <>
          <Divider label={t("compliance-intake-representative")} labelPosition="left" />
          <Group grow>
            <TextInput
              label={t("compliance-intake-given-names")}
              value={form.rep_given_names}
              onChange={(e) => setField("rep_given_names", e.currentTarget.value)}
            />
            <TextInput
              label={t("compliance-intake-paternal-surname")}
              value={form.rep_paternal_surname}
              onChange={(e) => setField("rep_paternal_surname", e.currentTarget.value)}
            />
            <TextInput
              label={t("compliance-intake-maternal-surname")}
              value={form.rep_maternal_surname}
              onChange={(e) => setField("rep_maternal_surname", e.currentTarget.value)}
            />
          </Group>
          <Group grow>
            <TextInput
              label={t("compliance-intake-date-of-birth")}
              placeholder="YYYY-MM-DD"
              value={form.rep_date_of_birth}
              onChange={(e) => setField("rep_date_of_birth", e.currentTarget.value)}
            />
            <TextInput
              label="RFC"
              value={form.rep_rfc}
              onChange={(e) => setField("rep_rfc", e.currentTarget.value)}
            />
            <TextInput
              label="CURP"
              value={form.rep_curp}
              onChange={(e) => setField("rep_curp", e.currentTarget.value)}
            />
          </Group>
          <Group grow>
            <NativeSelect
              label={t("compliance-intake-id-type")}
              data={idOptions}
              value={form.rep_id_document_type}
              onChange={(e) =>
                setField("rep_id_document_type", e.currentTarget.value)
              }
            />
            <TextInput
              label={t("compliance-intake-id-authority")}
              value={form.rep_id_issuing_authority}
              onChange={(e) =>
                setField("rep_id_issuing_authority", e.currentTarget.value)
              }
            />
            <TextInput
              label={t("compliance-intake-id-number")}
              value={form.rep_id_document_number}
              onChange={(e) =>
                setField("rep_id_document_number", e.currentTarget.value)
              }
            />
          </Group>
        </>
      )}

      <Divider label={t("compliance-intake-controller")} labelPosition="left" />
      {!isMoral && (
        <Switch
          label={t("compliance-intake-own-controller")}
          checked={form.is_own_controller}
          onChange={(e) => setField("is_own_controller", e.currentTarget.checked)}
        />
      )}
      {(isMoral || !form.is_own_controller) && (
        <Stack gap="sm">
          {form.controllers.map((row, index) => (
            <Group key={index} align="flex-end" wrap="nowrap" gap="xs">
              <TextInput
                style={{ flex: 1 }}
                label={
                  index === 0 ? t("compliance-intake-controller-name") : undefined
                }
                value={row.name}
                onChange={(e) =>
                  setController(index, "name", e.currentTarget.value)
                }
              />
              <TextInput
                style={{ flex: 1 }}
                label={index === 0 ? "RFC" : undefined}
                value={row.rfc}
                onChange={(e) =>
                  setController(index, "rfc", e.currentTarget.value)
                }
              />
              <TextInput
                style={{ flex: 1 }}
                label={index === 0 ? t("compliance-intake-ownership") : undefined}
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

      <Button onClick={handleSave} loading={saving} mt="xs">
        {t("compliance-intake-save")}
      </Button>
    </Stack>
  );
}
