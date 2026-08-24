import React, { useCallback, useEffect, useRef, useState } from "react";
import { useLoaderData } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Loader, Text } from "@mantine/core";

import { MifielWidget } from "../../components/MifielWidget/MifielWidget";
import {
  getPublicSignatureRequest,
  TPublicSignatureRequest,
} from "../../modules/apiCalls";

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 2 * 60 * 1000;

const TERMINAL_STATUSES = new Set([
  "signed",
  "rejected",
  "expired",
  "deleted",
  "error",
]);

export default function SignaturePage() {
  const loaderData = useLoaderData() as TPublicSignatureRequest | null;
  const { t } = useTranslation();

  const [liveData, setLiveData] = useState<TPublicSignatureRequest | null>(
    loaderData
  );
  const [signSuccessSeen, setSignSuccessSeen] = useState(false);
  const [signErrorSeen, setSignErrorSeen] = useState(false);
  const [timedOut, setTimedOut] = useState(false);

  const startedAtRef = useRef(Date.now());

  const shouldPoll = Boolean(
    liveData && !TERMINAL_STATUSES.has(liveData.status)
  );

  useEffect(() => {
    if (!liveData || !shouldPoll) return;

    const interval = setInterval(async () => {
      if (Date.now() - startedAtRef.current > POLL_TIMEOUT_MS) {
        setTimedOut(true);
        clearInterval(interval);
        return;
      }
      try {
        const fresh = await getPublicSignatureRequest(liveData.id);
        setLiveData(fresh);
      } catch (e) {
        console.log(e);
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveData?.id, shouldPoll]);

  const onSignSuccess = useCallback(() => {
    setSignSuccessSeen(true);
    setSignErrorSeen(false);
  }, []);

  const onSignError = useCallback((detail: unknown) => {
    console.error("Mifiel signError", detail);
    setSignErrorSeen(true);
  }, []);

  if (!liveData) {
    return (
      <Centered>
        <Text c="dimmed" ta="center" maw={480}>
          {t("esign-link-invalid")}
        </Text>
      </Centered>
    );
  }

  if (liveData.status === "pending" && !liveData.widget_ready) {
    return (
      <Centered>
        <Loader size="sm" mb="sm" />
        <Text c="dimmed" ta="center" maw={480}>
          {t(
            timedOut ? "esign-preparing-timeout" : "esign-preparing-document"
          )}
        </Text>
      </Centered>
    );
  }

  if (liveData.status === "pending" && liveData.widget_ready && liveData.widget_id) {
    return (
      <div
        className="flex relative min-h-screen w-full overflow-x-hidden flex-col items-center px-4 py-8"
        style={{ backgroundColor: "var(--bg-color)" }}
      >
        <div className="w-full md:max-w-[720px]">
          <Text fw={600} size="lg" ta="center" mb="xs">
            {liveData.title}
          </Text>
          <Text c="dimmed" ta="center" mb="lg">
            {liveData.organization_name}
          </Text>

          {signSuccessSeen && (
            <Text c="dimmed" ta="center" mb="sm">
              {t("esign-signing-in-progress")}
            </Text>
          )}
          {signErrorSeen && (
            <Text c="red" ta="center" mb="sm">
              {t("esign-sign-error")}
            </Text>
          )}

          <MifielWidget
            widgetId={liveData.widget_id}
            environment={liveData.mifiel_environment}
            onSignSuccess={onSignSuccess}
            onSignError={onSignError}
          />
        </div>
      </div>
    );
  }

  if (liveData.status === "signed") {
    return (
      <Centered>
        <Text ta="center" maw={480}>
          {t("esign-signed-success", { name: liveData.signatory_name })}
        </Text>
      </Centered>
    );
  }

  const terminalKey =
    liveData.status === "rejected"
      ? "esign-rejected"
      : liveData.status === "expired"
        ? "esign-expired"
        : liveData.status === "deleted"
          ? "esign-deleted"
          : "esign-error";

  return (
    <Centered>
      <Text c="dimmed" ta="center" maw={480}>
        {t(terminalKey)}
      </Text>
    </Centered>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <main
      className="flex relative min-h-screen w-full overflow-x-hidden items-center justify-center p-6"
      style={{ backgroundColor: "var(--bg-color)" }}
    >
      <div className="flex flex-col items-center">{children}</div>
    </main>
  );
}
