import React, { useEffect } from "react";
import { useTranslation } from "react-i18next";
import MindMapper from "../../components/Plugins/MindMapper";
import { AppPage } from "../../components/AppPage/AppPage";
import { useStore } from "../../modules/store";

export default function WorkflowsPage() {
  const { t } = useTranslation();
  const startup = useStore((state) => state.startup);

  useEffect(() => {
    startup();
  }, []);

  return (
    <AppPage title={t("workflows")} pad={false}>
      <MindMapper />
    </AppPage>
  );
}
