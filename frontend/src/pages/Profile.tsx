import { type ChangeEvent, useState } from "react";

import {
  type ProfileDocument,
  type ProfileDocumentDetail,
  fetchDocument,
  uploadDocument,
} from "../api";
import { t } from "../i18n";

type State = "idle" | "sending" | "done" | "error";

export default function Profile() {
  const [state, setState] = useState<State>("idle");
  const [document, setDocument] = useState<ProfileDocument | null>(null);
  const [detail, setDetail] = useState<ProfileDocumentDetail | null>(null);
  const [error, setError] = useState("");
  const [showText, setShowText] = useState(false);

  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setState("sending");
    setError("");
    setDetail(null);
    setShowText(false);

    try {
      const created = await uploadDocument(file);
      setDocument(created);
      setState("done");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
      setState("error");
    } finally {
      event.target.value = "";
    }
  };

  const reveal = async () => {
    if (!document) {
      return;
    }
    if (detail) {
      setShowText((value) => !value);
      return;
    }
    try {
      setDetail(await fetchDocument(document.id));
      setShowText(true);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
      setState("error");
    }
  };

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t("profile.title")}</h1>

      <div className="rounded-xl border border-neutral-200 bg-white p-5">
        <h2 className="font-medium">{t("profile.upload.title")}</h2>
        <p className="mt-1 text-sm text-neutral-600">{t("profile.upload.hint")}</p>

        <label className="mt-4 inline-block cursor-pointer rounded-lg bg-neutral-900 px-4 py-2 text-sm text-white hover:bg-neutral-700">
          {state === "sending" ? t("profile.upload.sending") : t("profile.upload.action")}
          <input
            accept=".pdf,.docx,.md,.markdown,.txt"
            className="hidden"
            disabled={state === "sending"}
            onChange={onFile}
            type="file"
          />
        </label>

        {state === "done" && document ? (
          <div className="mt-4 space-y-2">
            <p className="text-sm text-emerald-700">
              {t("profile.upload.done", { count: document.char_count })}
            </p>
            <p className="text-xs text-neutral-500">{document.filename}</p>
            <button
              className="text-xs underline underline-offset-4"
              onClick={reveal}
              type="button"
            >
              {t("profile.preview.title")}
            </button>
          </div>
        ) : null}

        {state === "error" ? (
          <p className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {t("profile.upload.error", { reason: error })}
          </p>
        ) : null}
      </div>

      {showText && detail ? (
        <div className="rounded-xl border border-neutral-200 bg-white p-5">
          <h2 className="font-medium">{t("profile.preview.title")}</h2>
          <p className="mt-1 text-xs text-neutral-500">{t("profile.preview.hint")}</p>
          <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-neutral-50 p-4 text-xs leading-relaxed text-neutral-800">
            {detail.extracted_text}
          </pre>
        </div>
      ) : null}
    </section>
  );
}
