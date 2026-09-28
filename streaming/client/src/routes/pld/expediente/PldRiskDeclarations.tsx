import { useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { Button, Radio, Stack, Text, TextInput } from "@mantine/core";
import { saveMyPldRiskDeclarations, TMyPldExpedient } from "../../../modules/apiCalls";

function asBool(value: unknown): boolean | null {
  if (value === true || value === false) return value;
  return null;
}

function YesNo({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean | null;
  onChange: (next: boolean) => void;
}) {
  const { t } = useTranslation();
  return (
    <Radio.Group
      label={label}
      value={value === null ? "" : value ? "yes" : "no"}
      onChange={(next) => onChange(next === "yes")}
    >
      <Stack gap={6} mt={6}>
        <Radio value="yes" label={t("compliance-risk-yes")} />
        <Radio value="no" label={t("compliance-risk-no")} />
      </Stack>
    </Radio.Group>
  );
}

export function PldRiskDeclarations({
  row,
  onSaved,
  onContinue,
}: {
  row: TMyPldExpedient;
  onSaved: (row: TMyPldExpedient) => void;
  onContinue?: () => void;
}) {
  const { t } = useTranslation();
  const meta = row.metadata || {};
  const moral = row.person_type === "persona_moral";
  const [pep, setPep] = useState<boolean | null>(asBool(meta.declares_pep));
  const [partners, setPartners] = useState<boolean | null>(asBool(meta.partners_pep));
  const [names, setNames] = useState(String(meta.partners_pep_names || ""));
  const [thirdParty, setThirdParty] = useState<boolean | null>(
    asBool(meta.third_party_payments)
  );
  const [foreign, setForeign] = useState<boolean | null>(asBool(meta.foreign_operations));
  const [countries, setCountries] = useState(String(meta.foreign_countries || ""));
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (pep === null || thirdParty === null || foreign === null) {
      toast.error(t("compliance-risk-missing"));
      return;
    }
    if (moral && partners === null) {
      toast.error(t("compliance-risk-missing"));
      return;
    }
    if (moral && partners && !names.trim()) {
      toast.error(t("compliance-risk-missing"));
      return;
    }
    if (foreign && !countries.trim()) {
      toast.error(t("compliance-risk-missing"));
      return;
    }
    setBusy(true);
    try {
      const saved = await saveMyPldRiskDeclarations(row.id, {
        declares_pep: pep,
        partners_pep: moral ? partners : false,
        partners_pep_names: moral && partners ? names.trim() : null,
        third_party_payments: thirdParty,
        foreign_operations: foreign,
        foreign_countries: foreign ? countries.trim() : null,
      });
      onSaved(saved);
      onContinue?.();
    } catch {
      toast.error(t("compliance-risk-error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack gap="sm">
      <Text fw={600}>{t("compliance-risk-title")}</Text>
      <YesNo label={t("compliance-risk-pep")} value={pep} onChange={setPep} />
      {moral ? (
        <>
          <YesNo
            label={t("compliance-risk-partners")}
            value={partners}
            onChange={setPartners}
          />
          {partners ? (
            <TextInput
              label={t("compliance-risk-partners-who")}
              value={names}
              onChange={(event) => setNames(event.currentTarget.value)}
            />
          ) : null}
        </>
      ) : null}
      <YesNo
        label={t("compliance-risk-third-party")}
        value={thirdParty}
        onChange={setThirdParty}
      />
      <YesNo
        label={t("compliance-risk-foreign")}
        value={foreign}
        onChange={setForeign}
      />
      {foreign ? (
        <TextInput
          label={t("compliance-risk-countries")}
          value={countries}
          onChange={(event) => setCountries(event.currentTarget.value)}
        />
      ) : null}
      <Button color="violet" fullWidth loading={busy} onClick={save}>
        {t("compliance-doc-continue")}
      </Button>
    </Stack>
  );
}
