import React from "react";
import {
  IconFileSpreadsheet,
  IconFileText,
  IconFileTypePdf,
  IconPresentation,
} from "@tabler/icons-react";

export function documentFileExtension(name: string, contentType = ""): string {
  const fromName = name.split(".").pop()?.toLowerCase() || "";
  if (fromName && fromName.length <= 5 && fromName !== name.toLowerCase()) {
    return fromName;
  }
  const ct = contentType.toLowerCase();
  if (ct.includes("pdf")) return "pdf";
  if (ct.includes("spreadsheet") || ct.includes("excel")) return "xlsx";
  if (ct.includes("presentation") || ct.includes("powerpoint")) return "pptx";
  if (ct.includes("wordprocessing") || ct.includes("msword")) return "docx";
  return "file";
}

export type DocumentFileMeta = {
  ext: string;
  color: string;
  label: string;
};

export function getDocumentFileMeta(
  name: string,
  contentType = ""
): DocumentFileMeta {
  const ext = documentFileExtension(name, contentType);
  switch (ext) {
    case "pdf":
      return { ext, color: "red", label: "PDF" };
    case "xlsx":
    case "xls":
    case "csv":
      return { ext, color: "teal", label: ext.toUpperCase() };
    case "pptx":
    case "ppt":
      return { ext, color: "orange", label: ext.toUpperCase() };
    case "docx":
    case "doc":
      return { ext, color: "blue", label: ext.toUpperCase() };
    default:
      return { ext, color: "gray", label: ext.toUpperCase() || "FILE" };
  }
}

export function DocumentFileIcon({
  name,
  contentType = "",
  size = 20,
  color,
}: {
  name: string;
  contentType?: string;
  size?: number;
  color?: string;
}) {
  const meta = getDocumentFileMeta(name, contentType);
  const iconColor = color ?? `var(--mantine-color-${meta.color}-5)`;
  switch (meta.ext) {
    case "pdf":
      return <IconFileTypePdf size={size} color={iconColor} />;
    case "xlsx":
    case "xls":
    case "csv":
      return <IconFileSpreadsheet size={size} color={iconColor} />;
    case "pptx":
    case "ppt":
      return <IconPresentation size={size} color={iconColor} />;
    default:
      return <IconFileText size={size} color={iconColor} />;
  }
}
