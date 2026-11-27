import { type ChangeEvent, useEffect, useState } from "react";

import {
  type Profile,
  type ProfileDocument,
  type ProfileDocumentDetail,
  fetchDocument,
  fetchProfile,
  generateAssessment,
  saveProfile,
  uploadDocument,
} from "../api";
import { t } from "../i18n";

type UploadState = "idle" | "sending" | "done" | "error";
type SaveState = "idle" | "saving" | "saved" | "error";

type FormState = {
  years: string;
  roles: string;
  cities: string;
  salary: string;
  strengths: string;
  gaps: string;
  positioning: string;
  fit: string;
};

const EMPTY_FORM: FormState = {
  years: "",
  roles: "",
  cities: "",
  salary: "",
  strengths: "",
  gaps: "",
  positioning: "",
  fit: "",
};

function toForm(profile: Profile): FormState {
  return {
    years: profile.years_experience === null ? "" : String(profile.years_experience),
    roles: profile.target_roles.join(", "),
    cities: profile.target_cities.join(", "),
    salary: profile.salary_floor === null ? "" : String(profile.salary_floor),
    strengths: profile.strengths ?? "",
    gaps: profile.gaps ?? "",
    positioning: profile.positioning ?? "",
    fit: profile.target_fit ?? "",
  };
}

function splitList(value: string): string[] {
  return value
    .split(/[,，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function numberOrNull(value: string): number | null {
  const parsed = Number.parseInt(value.trim(), 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function textOrNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

export default function Profile() {
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [document, setDocument] = useState<ProfileDocument | null>(null);
  const [detail, setDetail] = useState<ProfileDocumentDetail | null>(null);
  const [showText, setShowText] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [assessing, setAssessing] = useState(false);
  const [assessError, setAssessError] = useState("");
  const [assessNote, setAssessNote] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchProfile()
      .then((profile) => {
        if (!cancelled) {
          setForm(toForm(profile));
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const set = (field: keyof FormState) => (value: string) =>
    setForm((current) => ({ ...current, [field]: value }));

  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setUploadState("sending");
    setUploadError("");
    setDetail(null);
    setShowText(false);

    try {
      setDocument(await uploadDocument(file));
      setUploadState("done");
    } catch (failure) {
      setUploadError(failure instanceof Error ? failure.message : String(failure));
      setUploadState("error");
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
      setUploadError(failure instanceof Error ? failure.message : String(failure));
      setUploadState("error");
    }
  };

  const save = async () => {
    setSaveState("saving");
    try {
      const saved = await saveProfile({
        years_experience: numberOrNull(form.years),
        target_roles: splitList(form.roles),
        target_cities: splitList(form.cities),
        salary_floor: numberOrNull(form.salary),
        strengths: textOrNull(form.strengths),
        gaps: textOrNull(form.gaps),
        positioning: textOrNull(form.positioning),
        target_fit: textOrNull(form.fit),
      });
      setForm(toForm(saved));
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
  };

  const assess = async () => {
    setAssessing(true);
    setAssessError("");
    setAssessNote("");
    try {
      const draft = await generateAssessment();
      const empty =
        draft.strengths.length === 0 &&
        draft.gaps.length === 0 &&
        draft.positioning === "" &&
        draft.target_fit === "";

      setForm((current) => ({
        ...current,
        strengths: draft.strengths.join("\n") || current.strengths,
        gaps: draft.gaps.join("\n") || current.gaps,
        positioning: draft.positioning || current.positioning,
        fit: draft.target_fit || current.fit,
      }));
      setAssessNote(empty ? t("profile.assessEmpty") : t("profile.assessHint"));
    } catch (failure) {
      setAssessError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setAssessing(false);
    }
  };

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t("profile.title")}</h1>

      <div className="rounded-xl border border-neutral-200 bg-white p-5">
        <h2 className="font-medium">{t("profile.upload.title")}</h2>
        <p className="mt-1 text-sm text-neutral-600">{t("profile.upload.hint")}</p>

        <label className="mt-4 inline-block cursor-pointer rounded-lg bg-neutral-900 px-4 py-2 text-sm text-white hover:bg-neutral-700">
          {uploadState === "sending" ? t("profile.upload.sending") : t("profile.upload.action")}
          <input
            accept=".pdf,.docx,.md,.markdown,.txt"
            className="hidden"
            disabled={uploadState === "sending"}
            onChange={onFile}
            type="file"
          />
        </label>

        {uploadState === "done" && document ? (
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

        {uploadState === "error" ? (
          <p className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {t("profile.upload.error", { reason: uploadError })}
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

      <div className="space-y-4 rounded-xl border border-neutral-200 bg-white p-5">
        <h2 className="font-medium">{t("profile.fields.title")}</h2>

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("profile.fields.roles")} value={form.roles} onChange={set("roles")} />
          <Field label={t("profile.fields.cities")} value={form.cities} onChange={set("cities")} />
          <Field
            label={t("profile.fields.salary")}
            type="number"
            value={form.salary}
            onChange={set("salary")}
          />
          <Field
            label={t("profile.fields.years")}
            type="number"
            value={form.years}
            onChange={set("years")}
          />
        </div>

        <Area label={t("profile.fields.strengths")} value={form.strengths} onChange={set("strengths")} />
        <Area label={t("profile.fields.gaps")} value={form.gaps} onChange={set("gaps")} />
        <Area
          label={t("profile.fields.positioning")}
          value={form.positioning}
          onChange={set("positioning")}
        />
        <Area label={t("profile.fields.fit")} value={form.fit} onChange={set("fit")} />

        <div className="flex flex-wrap items-center gap-3">
          <button
            className="rounded-lg bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-40"
            disabled={saveState === "saving"}
            onClick={save}
            type="button"
          >
            {saveState === "saving" ? t("profile.saving") : t("profile.save")}
          </button>
          <button
            className="rounded-lg border border-neutral-300 px-4 py-2 text-sm disabled:opacity-40"
            disabled={assessing}
            onClick={assess}
            type="button"
          >
            {assessing ? t("profile.assessing") : t("profile.assess")}
          </button>
          {saveState === "saved" ? (
            <span className="text-sm text-emerald-700">{t("profile.saved")}</span>
          ) : null}
          {saveState === "error" ? (
            <span className="text-sm text-red-700">{t("profile.saveError")}</span>
          ) : null}
          {assessNote ? <span className="text-xs text-neutral-500">{assessNote}</span> : null}
          {assessError ? (
            <span className="text-sm text-red-700">
              {t("profile.assessError", { reason: assessError })}
            </span>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "number";
}) {
  return (
    <label className="block text-sm">
      <span className="text-neutral-600">{label}</span>
      <input
        className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 outline-none focus:border-neutral-500"
        onChange={(event) => onChange(event.target.value)}
        type={type}
        value={value}
      />
    </label>
  );
}

function Area({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-sm">
      <span className="text-neutral-600">{label}</span>
      <textarea
        className="mt-1 min-h-24 w-full rounded-lg border border-neutral-300 px-3 py-2 outline-none focus:border-neutral-500"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  );
}
