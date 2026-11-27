import { type FormEvent, useState } from "react";

import { pasteJob } from "../api";
import { t } from "../i18n";

type PasteState = "idle" | "sending" | "accepted" | "duplicate" | "error";

/** "zero_width_chars_removed:3" -> a translated line. */
function flagLabel(flag: string): string {
  const [code, count] = flag.split(":");
  return t(`gate.${code}`, { count: count ?? "" });
}

export default function PastePanel({ onImported }: { onImported: () => void }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [state, setState] = useState<PasteState>("idle");
  const [title, setTitle] = useState("");
  const [flags, setFlags] = useState<string[]>([]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!text.trim()) {
      return;
    }

    setState("sending");
    try {
      const result = await pasteJob(text);
      setFlags(result.flags);
      setTitle(result.job?.title ?? "");

      if (result.outcome === "accepted") {
        setState("accepted");
        setText("");
        onImported();
      } else {
        setState("duplicate");
      }
    } catch {
      setState("error");
    }
  };

  return (
    <section className="rounded-xl border border-neutral-200 bg-white">
      <button
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        {open ? t("paste.close") : t("paste.open")}
        <span aria-hidden="true" className="text-neutral-400">
          {open ? "−" : "+"}
        </span>
      </button>

      {open ? (
        <form className="space-y-3 border-t border-neutral-200 p-4" onSubmit={onSubmit}>
          <textarea
            className="min-h-40 w-full rounded-lg border border-neutral-300 p-3 text-sm outline-none focus:border-neutral-500"
            onChange={(event) => setText(event.target.value)}
            placeholder={t("paste.placeholder")}
            value={text}
          />
          <div className="flex items-center gap-3">
            <button
              className="rounded-lg bg-neutral-900 px-4 py-2 text-sm text-white hover:bg-neutral-700 disabled:opacity-40"
              disabled={state === "sending" || text.trim() === ""}
              type="submit"
            >
              {state === "sending" ? t("paste.sending") : t("paste.action")}
            </button>
            {state === "accepted" ? (
              <span className="text-sm text-emerald-700">
                {t("paste.accepted", { title })}
              </span>
            ) : null}
            {state === "duplicate" ? (
              <span className="text-sm text-amber-700">
                {t("paste.duplicate", { title })}
              </span>
            ) : null}
            {state === "error" ? (
              <span className="text-sm text-red-700">{t("paste.error")}</span>
            ) : null}
          </div>

          {flags.length > 0 ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
              <p className="font-medium">{t("paste.flags", { count: flags.length })}</p>
              <ul className="mt-1 list-inside list-disc">
                {flags.map((flag) => (
                  <li key={flag}>{flagLabel(flag)}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </form>
      ) : null}
    </section>
  );
}
