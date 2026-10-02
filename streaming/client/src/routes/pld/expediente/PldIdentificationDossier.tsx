import { ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { Alert, Badge, Button, Card, Checkbox, Group, Loader, Stack, Stepper, Text, Title } from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
import { IconAlertTriangle, IconCircleCheck, IconDownload, IconSignature } from "@tabler/icons-react";
import {
  confirmMyPldDocuments,
  downloadMyPldPacket,
  listMyPldExpedients,
  regenerateMyPldPacket,
  rerunMyPldPrequalification,
  TMyPldExpedient,
} from "../../../modules/apiCalls";
import { PldClarificationRequests } from "./PldClarificationRequests";
import { PldNoticeStep } from "./PldNoticeStep";
import { PldPpeStep } from "./PldPpeStep";
import { PldRiskDeclarations } from "./PldRiskDeclarations";

const MORAL_CHECKS = [
  { code: "rfc_mismatch", key: "compliance-sign-check-rfc" },
  { code: "legal_name_mismatch", key: "compliance-sign-check-name" },
  { code: "address_proof_stale", key: "compliance-sign-check-address" },
  { code: "id_expired_or_unreadable", key: "compliance-sign-check-representative" },
  { code: "controller_missing", key: "compliance-sign-check-controller" },
];

const LIST_LABELS: Record<string, string> = {
  onu_csnu: "ONU",
  sat_69b: "SAT 69-B",
  sat_69b_bis: "SAT 69-B Bis",
  sat_69_firmes: "SAT 69 firmes",
  sat_69_no_localizados: "SAT 69 no localizados",
  sat_69_exigibles: "SAT 69 exigibles",
  sat_69_sentencias: "SAT 69 sentencias",
  sat_69_csd: "SAT 69 CSD",
};

type StepId = "data" | "validation" | "lists" | "ppe" | "score" | "notice" | "sign";

const STEP_LABEL: Record<StepId, string> = {
  data: "compliance-step-data",
  validation: "compliance-step-validation",
  lists: "compliance-step-lists",
  ppe: "compliance-step-ppe",
  score: "compliance-step-score",
  notice: "compliance-step-notice",
  sign: "compliance-step-sign",
};

export function stepIds(row: TMyPldExpedient): StepId[] {
  const ids: StepId[] = ["data", "validation", "lists"];
  if (row.ppe_screening_enabled) ids.push("ppe");
  ids.push("score");
  if (row.vulnerable_activity) ids.push("notice");
  ids.push("sign");
  return ids;
}

export function stepLabelKeys(row: TMyPldExpedient): string[] {
  return stepIds(row).map((id) => STEP_LABEL[id]);
}

function riskDeclared(row: TMyPldExpedient) {
  const meta = row.metadata || {};
  if (typeof meta.declares_pep !== "boolean") return false;
  if (typeof meta.third_party_payments !== "boolean") return false;
  if (typeof meta.foreign_operations !== "boolean") return false;
  if (row.person_type === "persona_moral" && typeof meta.partners_pep !== "boolean") {
    return false;
  }
  return true;
}

export function flowFurthest(row: TMyPldExpedient): number {
  const ids = stepIds(row);
  const at = (id: StepId) => ids.indexOf(id);
  const status = row.expedient?.status || "";
  const prequal = row.expedient?.prequalification_status;
  if (status === "waiting_sign" || status === "signed" || status === "delivered") {
    return at("sign");
  }
  if (status === "cross_reference") {
    if (row.expedient?.screening_status !== "succeeded") return at("lists");
    if (row.ppe_screening_enabled && row.expedient?.ppe_status !== "succeeded") {
      return at("ppe");
    }
    if (!riskDeclared(row)) return at("score");
    if (row.vulnerable_activity && row.metadata?.notice_invoices_done !== true) {
      return at("notice");
    }
    return at("sign");
  }
  if (
    prequal === "pending" ||
    prequal === "succeeded" ||
    prequal === "failed" ||
    status === "action_required"
  ) {
    return at("validation");
  }
  return at("data");
}

export function ProcessBar({
  furthest,
  current,
  labels,
  onPick,
}: {
  furthest: number;
  current: number;
  labels: string[];
  onPick: (step: number) => void;
}) {
  const narrow = useMediaQuery("(max-width: 48em)");
  return (
    <Stepper
      active={furthest}
      onStepClick={(step) => {
        if (step <= furthest) onPick(step);
      }}
      allowNextStepsSelect={false}
      orientation="horizontal"
      size="xs"
      iconSize={22}
      styles={{
        root: { width: "100%" },
        steps: narrow
          ? { flexWrap: "wrap", justifyContent: "center", rowGap: 16, width: "100%" }
          : { flexWrap: "nowrap" },
        step: {
          flexDirection: "column",
          alignItems: "center",
          ...(narrow ? { flex: "0 0 30%", maxWidth: 110 } : {}),
        },
        stepBody: { marginInlineStart: 0, marginTop: 4 },
        separator: narrow ? { display: "none" } : { marginTop: 11 },
      }}
    >
      {labels.map((label, index) => (
        <Stepper.Step
          key={label}
          label={label}
          styles={{
            stepLabel: {
              fontSize: 11,
              textAlign: "center",
              fontWeight: index === current ? 700 : 500,
              color:
                index === current ? "var(--mantine-color-violet-3)" : undefined,
            },
            stepIcon:
              index === current
                ? { boxShadow: "0 0 0 2px var(--mantine-color-violet-4)" }
                : undefined,
          }}
        />
      ))}
    </Stepper>
  );
}

function ListsResult({
  checks,
  listNames,
}: {
  checks: { role: string; name: string; rfc: string; hit_count: number }[];
  listNames: string[];
}) {
  const { t } = useTranslation();
  const clear = checks.length > 0 && checks.every((item) => item.hit_count === 0);
  return (
    <Stack gap="md">
      {clear ? (
        <Alert color="teal" variant="light" icon={<IconCircleCheck size={18} />}>
          {t("compliance-screening-clear")}
        </Alert>
      ) : null}
      {listNames.length > 0 ? (
        <Stack gap={8}>
          <Text size="sm" fw={600}>
            {t("compliance-screening-lists")}
          </Text>
          <Group gap={6}>
            {listNames.map((name) => (
              <Badge key={name} variant="outline" color="gray" style={{ textTransform: "none" }}>
                {name}
              </Badge>
            ))}
          </Group>
        </Stack>
      ) : null}
      <Stack gap="xs">
        {checks.map((check) => (
          <Card key={`${check.role}-${check.rfc}`} withBorder radius="md" p="sm">
            <Group justify="space-between" align="center" wrap="nowrap" gap="sm">
              <Stack gap={2} style={{ minWidth: 0 }}>
                <Text size="xs" c="dimmed">
                  {t(`compliance-screening-role-${check.role}`)}
                </Text>
                {check.name ? (
                  <Text size="sm" fw={600} style={{ overflowWrap: "anywhere" }}>
                    {check.name}
                  </Text>
                ) : null}
                <Text size="xs" c="dimmed">
                  {check.rfc}
                </Text>
              </Stack>
              <Badge
                variant="light"
                color={check.hit_count === 0 ? "teal" : "red"}
                style={{ flexShrink: 0, textTransform: "none" }}
              >
                {check.hit_count === 0
                  ? t("compliance-screening-hits_zero")
                  : t("compliance-screening-hits", { count: check.hit_count })}
              </Badge>
            </Group>
          </Card>
        ))}
      </Stack>
    </Stack>
  );
}

function StepContinue({
  onClick,
  disabled,
  loading,
}: {
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
}) {
  const { t } = useTranslation();
  if (!onClick) return null;
  return (
    <Button color="violet" fullWidth disabled={disabled} loading={loading} onClick={onClick}>
      {t("compliance-doc-continue")}
    </Button>
  );
}

function consultedListNames(
  searches: { lists?: string[] }[] | undefined
): string[] {
  const seen: string[] = [];
  for (const search of searches || []) {
    for (const slug of search.lists || []) {
      const label = LIST_LABELS[slug] || slug;
      if (!seen.includes(label)) seen.push(label);
    }
  }
  return seen;
}

const FISICA_CHECKS = [
  { code: "rfc_mismatch", key: "compliance-sign-check-rfc" },
  { code: "curp_mismatch", key: "compliance-sign-check-curp" },
  { code: "legal_name_mismatch", key: "compliance-sign-check-name" },
  { code: "address_proof_stale", key: "compliance-sign-check-address" },
  { code: "id_expired_or_unreadable", key: "compliance-sign-check-id" },
];

export function PldIdentificationDossier({
  row,
  onSaved,
  onNext,
  headerExtra,
  forcedView,
  showBar = true,
}: {
  row: TMyPldExpedient;
  onSaved: (next: TMyPldExpedient) => void;
  onNext?: () => void;
  headerExtra?: ReactNode;
  forcedView?: number;
  showBar?: boolean;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const slots = row.document_slots || [];
  const required = slots.filter((slot) => slot.required);
  const pending = required.some(
    (slot) => !slot.document || slot.document.extraction_status === "pending"
  );
  const prequalPending = row.expedient?.prequalification_status === "pending";
  const screeningPending = row.expedient?.screening_status === "pending";
  const ppePending =
    Boolean(row.ppe_screening_enabled) && row.expedient?.ppe_status === "pending";
  const clarifyExtracting = (row.clarification_requests || []).some(
    (item) =>
      (item.status === "open" && item.document?.extraction_status === "pending") ||
      item.text_review === "reviewing"
  );
  const status = row.expedient?.status || "";
  const waitingSign = status === "waiting_sign";
  const signedDone = status === "signed" || status === "delivered";
  const packetStatus = row.expedient?.packet_status || "";
  const packetWriting = packetStatus === "writing";
  const packetReady = packetStatus === "ready" || Boolean(row.expedient?.packet_ready);
  const poll =
    pending ||
    prequalPending ||
    screeningPending ||
    ppePending ||
    clarifyExtracting ||
    waitingSign ||
    packetWriting;
  const onSavedRef = useRef(onSaved);
  onSavedRef.current = onSaved;

  useEffect(() => {
    if (!poll) return;
    let cancelled = false;
    const refresh = async () => {
      try {
        const data = await listMyPldExpedients();
        const next = (data.results || []).find((item) => item.id === row.id);
        if (!cancelled && next) onSavedRef.current(next);
      } catch {
        return;
      }
    };
    const timer = window.setInterval(refresh, 2500);
    void refresh();
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [poll, row.id]);
  const failed = required.some(
    (slot) => slot.document?.extraction_status === "failed"
  );
  const ready =
    required.length > 0 &&
    required.every((slot) => slot.document?.extraction_status === "succeeded");
  const prequal = row.expedient?.prequalification;
  const verdict = prequal?.verdict;
  const openRequests = (row.clarification_requests || []).filter(
    (item) => item.status === "open"
  );
  const prequalReady =
    row.expedient?.prequalification_status === "succeeded" &&
    verdict === "ready_for_list_screening" &&
    openRequests.length === 0;
  const [accepted, setAccepted] = useState(false);
  const [pickedStep, setPickedStep] = useState<number | null>(null);
  const confirmEnabled = ready && prequalReady && accepted && !busy;
  const alreadyCross = status === "cross_reference";
  const hideConfirm = alreadyCross || waitingSign || signedDone;
  const handleContinueValidation = async () => {
    if (!confirmEnabled) return;
    setBusy(true);
    try {
      const saved = await confirmMyPldDocuments(row.id);
      onSaved(saved);
      onNext?.();
    } catch {
      toast.error(t("compliance-dossier-confirm-error"));
    } finally {
      setBusy(false);
    }
  };

  const handleRetryPrequal = async () => {
    setBusy(true);
    try {
      const saved = await rerunMyPldPrequalification(row.id);
      if (saved) onSaved(saved);
    } catch {
      toast.error(t("compliance-prequal-rerun-error"));
    } finally {
      setBusy(false);
    }
  };

  const handleRegeneratePacket = async () => {
    setBusy(true);
    try {
      const saved = await regenerateMyPldPacket(row.id);
      onSaved(saved);
    } catch {
      toast.error(t("compliance-packet-regenerate-error"));
    } finally {
      setBusy(false);
    }
  };

  const handleDownloadPacket = async () => {
    setBusy(true);
    try {
      await downloadMyPldPacket(row.id);
    } catch {
      toast.error(t("compliance-sign-download-error"));
    } finally {
      setBusy(false);
    }
  };

  const signLayout = waitingSign || signedDone;
  const checks = row.person_type === "persona_moral" ? MORAL_CHECKS : FISICA_CHECKS;
  const findingByCode = new Map(
    (prequal?.debug?.findings || [])
      .filter((item) => item.code)
      .map((item) => [item.code as string, item.summary || ""])
  );
  const passedChecks = checks.filter((item) => !findingByCode.has(item.code));
  const signRejected =
    row.expedient?.signing?.status === "rejected" ||
    row.expedient?.signing?.status === "error";
  const listNames = consultedListNames(row.expedient?.screening?.searches);
  const furthest = flowFurthest(row);
  const ids = stepIds(row);
  const noticeAt = ids.indexOf("notice");
  const ppeAt = ids.indexOf("ppe");
  const scoreAt = ids.indexOf("score");
  const signAt = ids.indexOf("sign");
  const view =
    forcedView != null
      ? forcedView
      : pickedStep != null && pickedStep <= furthest
        ? pickedStep
        : furthest;
  const packetStarted = useRef(false);
  useEffect(() => {
    if (view !== signAt || signedDone || packetStatus) return;
    if (packetStarted.current) return;
    packetStarted.current = true;
    void regenerateMyPldPacket(row.id)
      .then((saved) => {
        if (saved) onSavedRef.current(saved);
      })
      .catch(() => {
        packetStarted.current = false;
      });
  }, [view, signAt, signedDone, packetStatus, row.id]);
  const stepLabels = stepLabelKeys(row).map((key) => t(key));
  const noticePanel =
    view === noticeAt ? (
      <PldNoticeStep row={row} onSaved={onSaved} onNext={onNext} />
    ) : null;
  const ppePanel =
    view === ppeAt ? (
      <PldPpeStep row={row} onSaved={onSaved} onContinue={onNext} />
    ) : null;
  const signPanel = (
    <Stack gap="sm">
      <Card withBorder radius="md" p="md">
        <Stack gap="sm">
          <Text fw={600}>{t("compliance-sign-title")}</Text>
          <Text size="sm" c="dimmed">
            {signedDone ? t("compliance-sign-done") : t("compliance-sign-intro")}
          </Text>
          {signRejected ? (
            <Alert color="yellow" variant="light" icon={<IconAlertTriangle size={16} />}>
              {t("compliance-sign-rejected")}
            </Alert>
          ) : null}
          {!signedDone && !row.expedient?.signing?.url && !packetWriting ? (
            <Group gap="xs">
              <Loader size={16} type="oval" color="violet" />
              <Text size="sm">{t("compliance-sign-preparing")}</Text>
            </Group>
          ) : null}
          {waitingSign && row.expedient?.signing?.url ? (
            <Button
              component="a"
              href={row.expedient.signing.url}
              color="violet"
              fullWidth
              leftSection={<IconSignature size={16} />}
            >
              {t("compliance-sign-cta")}
            </Button>
          ) : null}
          {packetWriting ? (
            <Group gap="xs">
              <Loader size={16} type="oval" color="violet" />
              <Text size="sm">{t("compliance-packet-writing")}</Text>
            </Group>
          ) : null}
          {packetStatus === "failed" ? (
            <Alert color="red" variant="light">
              {t("compliance-packet-failed")}
            </Alert>
          ) : null}
          {packetReady ? (
            <Button
              type="button"
              variant="default"
              fullWidth
              leftSection={<IconDownload size={16} />}
              loading={busy}
              onClick={handleDownloadPacket}
            >
              {t("compliance-sign-download")}
            </Button>
          ) : null}
          <Button
            type="button"
            variant="subtle"
            color="gray"
            fullWidth
            loading={busy || packetWriting}
            disabled={packetWriting}
            onClick={handleRegeneratePacket}
          >
            {t("compliance-packet-regenerate")}
          </Button>
        </Stack>
      </Card>
    </Stack>
  );

  if (alreadyCross) {
    return (
      <Stack gap="md" mt="md">
        {showBar ? (
          <ProcessBar furthest={furthest} current={view} labels={stepLabels} onPick={setPickedStep} />
        ) : null}
        {view === 0 ? (
          <Text size="sm">{t("compliance-step-data-body")}</Text>
        ) : null}
        {view === 1 ? (
          <Stack gap="sm">
            {prequal?.summary ? (
              <Alert
                color={verdict === "ready_for_list_screening" ? "teal" : "yellow"}
                variant="light"
              >
                {prequal.summary}
              </Alert>
            ) : (
              <Text size="sm">{t("compliance-dossier-ready")}</Text>
            )}
            <PldClarificationRequests row={row} onSaved={onSaved} />
            <Checkbox
              checked={Boolean(row.metadata?.truthfulness_accepted)}
              disabled
              label={t("compliance-consent-label")}
            />
            <StepContinue onClick={onNext} />
          </Stack>
        ) : null}
        {view === 2 ? (
          <Stack gap="sm">
            <ListsResult
              checks={row.expedient?.screening?.checks || []}
              listNames={listNames}
            />
            {screeningPending ? (
              <Alert
                color="violet"
                variant="light"
                icon={<Loader size={16} type="oval" color="currentColor" />}
              >
                {t("compliance-screening-running")}
              </Alert>
            ) : null}
            <StepContinue
              onClick={onNext}
              disabled={row.expedient?.screening_status !== "succeeded"}
            />
          </Stack>
        ) : null}
        {view === scoreAt && row.expedient?.screening_status === "succeeded" ? (
          <PldRiskDeclarations row={row} onSaved={onSaved} onContinue={onNext} />
        ) : null}
        {view === scoreAt && row.expedient?.screening_status !== "succeeded" ? (
          <StepContinue onClick={onNext} />
        ) : null}
        {ppePanel}
        {noticePanel}
        {view === signAt ? signPanel : null}
        {row.expedient?.screening_status === "failed" ? (
          <Alert color="red" variant="light">
            {t("compliance-screening-failed")}
          </Alert>
        ) : null}
        {view === 1 ? null : (
          <PldClarificationRequests row={row} onSaved={onSaved} openOnly />
        )}
      </Stack>
    );
  }

  if (signLayout) {
    return (
      <Stack gap="lg" mt="md">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Stack gap={6}>
            <Text size="sm" c="dimmed">
              {t("compliance-expediente-requested-by", {
                name: row.organization_name,
              })}
            </Text>
            <Title order={2}>{row.name}</Title>
            {status ? (
              <Badge variant="light" color="violet" w="fit-content">
                {t(`compliance-status-${status}`, { defaultValue: status })}
              </Badge>
            ) : null}
          </Stack>
          {headerExtra}
        </Group>
        {showBar ? (
          <ProcessBar furthest={furthest} current={view} labels={stepLabels} onPick={setPickedStep} />
        ) : null}
        {view === 0 ? <Text size="sm">{t("compliance-step-data-body")}</Text> : null}
        {view === 1 ? (
          <Stack gap="sm">
          <Card withBorder radius="md" p="md">
              <Group gap="sm" wrap="nowrap" align="flex-start" mb="sm">
                {passedChecks.length === checks.length ? (
                  <IconCircleCheck size={22} color="var(--mantine-color-teal-5)" />
                ) : (
                  <IconAlertTriangle size={22} color="var(--mantine-color-yellow-5)" />
                )}
                <Stack gap={0}>
                  {passedChecks.length === checks.length ? (
                    <Text size="sm" fw={600}>
                      {t(
                        row.person_type === "persona_moral"
                          ? "compliance-sign-checks-ok-moral"
                          : "compliance-sign-checks-ok-fisica"
                      )}
                    </Text>
                  ) : null}
                  <Text size="xs" c="dimmed">
                    {t("compliance-sign-checks-count", {
                      done: passedChecks.length,
                      total: checks.length,
                    })}
                  </Text>
                </Stack>
              </Group>
              <Stack gap={0}>
                {checks.map((item) => {
                  const failed = findingByCode.get(item.code);
                  return (
                    <Group
                      key={item.code}
                      gap="sm"
                      wrap="nowrap"
                      align="flex-start"
                      py={8}
                      style={{ borderTop: "1px solid var(--mantine-color-dark-4)" }}
                    >
                      {failed ? (
                        <IconAlertTriangle size={16} color="var(--mantine-color-yellow-5)" />
                      ) : (
                        <IconCircleCheck size={16} color="var(--mantine-color-teal-5)" />
                      )}
                      <Text size="sm">{failed || t(item.key)}</Text>
                    </Group>
                  );
                })}
              </Stack>
          </Card>
          <StepContinue onClick={onNext} />
          </Stack>
        ) : null}
        {view === 2 ? (
          <Stack gap="sm">
            <ListsResult
              checks={row.expedient?.screening?.checks || []}
              listNames={listNames}
            />
            <StepContinue
              onClick={onNext}
              disabled={row.expedient?.screening_status !== "succeeded"}
            />
          </Stack>
        ) : null}
        {view === scoreAt ? (
          <Stack gap="sm">
            {row.expedient?.screening?.summary ? (
              <Alert color="gray" variant="light">
                {row.expedient.screening.summary}
              </Alert>
            ) : null}
            <PldRiskDeclarations row={row} onSaved={onSaved} onContinue={onNext} />
          </Stack>
        ) : null}
        {ppePanel}
        {noticePanel}
        {view === signAt ? signPanel : null}
        <PldClarificationRequests row={row} onSaved={onSaved} openOnly />
      </Stack>
    );
  }

  return (
    <Stack gap="md" mt="md">
      {showBar ? (
        <ProcessBar furthest={furthest} current={view} labels={stepLabels} onPick={setPickedStep} />
      ) : null}
      {view === 0 ? <Text size="sm">{t("compliance-step-data-body")}</Text> : null}
      {view === 1 ? (
        <>
      <Title order={4}>{t("compliance-dossier-title")}</Title>
      <Text size="sm">{t("compliance-dossier-intro")}</Text>
      {pending && !failed && (
        <Alert
          color="violet"
          variant="light"
          icon={<Loader size={16} type="oval" color="currentColor" />}
        >
          {t("compliance-dossier-extracting")}
        </Alert>
      )}
      {failed && (
        <Alert color="red" variant="light">
          {t("compliance-dossier-failed")}
        </Alert>
      )}
      {prequalPending && ready && (
        <Alert
          color="violet"
          variant="light"
          icon={<Loader size={16} type="oval" color="currentColor" />}
        >
          {t("compliance-prequal-running")}
        </Alert>
      )}
      {row.expedient?.prequalification_status === "failed" && (
        <Stack gap="sm">
          <Alert color="red" variant="light">
            {t("compliance-prequal-failed")}
          </Alert>
          <Button variant="default" loading={busy} onClick={handleRetryPrequal}>
            {t("compliance-prequal-rerun")}
          </Button>
        </Stack>
      )}
      {prequal?.summary && row.expedient?.prequalification_status === "succeeded" && (
        <Alert
          color={verdict === "ready_for_list_screening" ? "teal" : "yellow"}
          variant="light"
        >
          {prequal.summary}
        </Alert>
      )}
      {row.expedient?.screening_status === "pending" && (
        <Alert
          color="violet"
          variant="light"
          icon={<Loader size={16} type="oval" color="currentColor" />}
        >
          {t("compliance-screening-running")}
        </Alert>
      )}
      {row.expedient?.screening_status === "failed" && (
        <Alert color="red" variant="light">
          {t("compliance-screening-failed")}
        </Alert>
      )}
      {row.expedient?.screening?.summary &&
        row.expedient?.screening_status === "succeeded" && (
          <Alert color="gray" variant="light">
            {row.expedient.screening.summary}
          </Alert>
        )}
      <PldClarificationRequests row={row} onSaved={onSaved} />
      {alreadyCross && openRequests.length === 0 ? (
        <Alert color="gray" variant="light">
          {t("compliance-dossier-next-lists")}
        </Alert>
      ) : null}
      {packetWriting ? (
        <Alert
          color="violet"
          variant="light"
          icon={<Loader size={16} type="oval" color="currentColor" />}
        >
          {t("compliance-packet-writing")}
        </Alert>
      ) : null}
      {packetStatus === "failed" ? (
        <Alert color="red" variant="light">
          {t("compliance-packet-failed")}
        </Alert>
      ) : null}
      {hideConfirm ? null : (
        <Checkbox
          checked={accepted}
          onChange={(event) => setAccepted(event.currentTarget.checked)}
          label={t("compliance-consent-label")}
        />
      )}
      <StepContinue
        onClick={handleContinueValidation}
        disabled={!confirmEnabled}
        loading={busy}
      />
        </>
      ) : null}
      {view === 2 ? (
        <Stack gap="sm">
          <ListsResult
            checks={row.expedient?.screening?.checks || []}
            listNames={listNames}
          />
          <StepContinue
            onClick={onNext}
            disabled={row.expedient?.screening_status !== "succeeded"}
          />
        </Stack>
      ) : null}
      {view === scoreAt ? (
        <PldRiskDeclarations row={row} onSaved={onSaved} onContinue={onNext} />
      ) : null}
      {ppePanel}
      {noticePanel}
      {view === signAt ? signPanel : null}
    </Stack>
  );
}
