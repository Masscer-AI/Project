import React, { useEffect, useState } from "react";
import mermaid from "mermaid";
import { useStore } from "../../modules/store";
import { Icon } from "../Icon/Icon";
import { SvgButton } from "../SvgButton/SvgButton";
import { useTranslation } from "react-i18next";
import { Modal } from "../Modal/Modal";
import "./CodeBlock.css";
import toast from "react-hot-toast";

export const CodeBlock = ({
  code,
  language,
}: {
  code: string;
  language: string;
}) => {
  if (language === "mermaid") {
    return <MermaidVisualizer code={code} />;
  }
  toast.success("Mermaid visualizer is not available yet");
  return <pre className={`language-${language}`}>{code}</pre>;
};

const MermaidVisualizer = ({ code }: { code: string }) => {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  const { theming } = useStore((s) => ({
    theming: s.theming,
  }));

  useEffect(() => {
    mermaid.initialize({ startOnLoad: true, theme: theming.mermaid as any });
    mermaid.run();
  }, []);

  const downloadSVG = async () => {
    const svg = await mermaid.render("myDiagram", code);
    const blob = new Blob([svg.svg], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "diagram.svg";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  useEffect(() => {
    if (expanded) {
      mermaid.run();
    }
  }, [expanded]);

  return (
    <div className="flex-y padding-big gap-medium mermaid-container">
      <section className="d-flex justify-center">
        <pre className="mermaid">{code}</pre>
      </section>

      <section className="d-flex justify-center gap-medium">
        <SvgButton
          onClick={downloadSVG}
          text={t("download-svg")}
          extraClass="bg-hovered active-on-hover pressable"
          svg={<Icon name="Download" size={20} />}
        />
        <SvgButton
          extraClass="bg-hovered active-on-hover pressable"
          onClick={() => {
            setExpanded(true);
          }}
          text={t("expand")}
          svg={<Icon name="Maximize2" size={20} />}
        />
        <Modal
          hide={() => {
            setExpanded(false);
          }}
          header={<h3 className="padding-medium">{t("mermaid-visualizer")}</h3>}
          visible={expanded}
        >
          <pre className="mermaid">{code}</pre>
        </Modal>
      </section>
    </div>
  );
};
