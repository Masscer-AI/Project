import type { TAttachment, TSource } from "../../types";

export type CompletionRef = {
  id: string;
  promptPreview: string;
  answerPreview: string;
  approved?: boolean;
};

export function parseCompletionContent(content: string): {
  prompt: string;
  answer: string;
} {
  const trimmed = (content || "").trim();
  const promptMatch = trimmed.match(/^PROMPT:\s*([\s\S]*?)(?:\n\nANSWER:|\nANSWER:)/i);
  const answerMatch = trimmed.match(/ANSWER:\s*([\s\S]*)$/i);
  return {
    prompt: (promptMatch?.[1] || trimmed).trim(),
    answer: (answerMatch?.[1] || "").trim(),
  };
}

function preview(text: string, max = 80): string {
  const t = (text || "").trim().replace(/\s+/g, " ");
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

export function collectCompletionRefs(
  attachments: TAttachment[] | undefined,
  sources: TSource[] | undefined
): CompletionRef[] {
  const byId = new Map<string, CompletionRef>();

  const merge = (id: string, partial: Partial<CompletionRef>) => {
    const key = String(id);
    const existing = byId.get(key);
    byId.set(key, {
      id: key,
      promptPreview: partial.promptPreview || existing?.promptPreview || "",
      answerPreview: partial.answerPreview || existing?.answerPreview || "",
      approved:
        partial.approved !== undefined ? partial.approved : existing?.approved,
    });
  };

  for (const att of attachments || []) {
    if ((att.type || "").toLowerCase() !== "completion") continue;
    const cid = String(att.completion_id ?? att.id ?? "");
    if (!/^\d+$/.test(cid)) continue;
    const prompt =
      (att as TAttachment & { prompt?: string }).prompt ||
      att.name ||
      "";
    const answer = (att as TAttachment & { answer?: string }).answer || "";
    merge(cid, {
      promptPreview: preview(prompt),
      answerPreview: preview(answer),
      approved: att.approved,
    });
  }

  for (const source of sources || []) {
    if ((source.model_name || "").toLowerCase() !== "completion") continue;
    const cid = String(source.model_id ?? "");
    if (!/^\d+$/.test(cid)) continue;
    const { prompt, answer } = parseCompletionContent(source.content || "");
    merge(cid, {
      promptPreview: preview(prompt),
      answerPreview: preview(answer),
    });
  }

  return Array.from(byId.values()).sort(
    (a, b) => parseInt(a.id, 10) - parseInt(b.id, 10)
  );
}
