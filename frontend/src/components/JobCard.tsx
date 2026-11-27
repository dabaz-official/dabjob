import { type FormEvent, useState } from "react";

import { type JobChanges, type JobSummary, updateJob } from "../api";
import { t } from "../i18n";

/**
 * The API returns a snippet with `<mark>` markers around the match. It is
 * rendered as elements rather than injected as HTML: the text originated in
 * a job posting, and a posting is attacker-controlled.
 */
function Snippet({ text }: { text: string }) {
  const chunks = text.split(/<mark>([\s\S]*?)<\/mark>/g);

  return (
    <>
      {chunks.map((chunk, index) =>
        index % 2 === 1 ? (
          <mark key={index} className="rounded bg-yellow-200 px-0.5 text-neutral-900">
            {chunk}
          </mark>
        ) : (
          <span key={index}>{chunk}</span>
        ),
      )}
    </>
  );
}

type Props = {
  job: JobSummary;
  onChanged: () => void;
};

export default function JobCard({ job, onChanged }: Props) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(job.title);
  const [company, setCompany] = useState(job.company_name);
  const [city, setCity] = useState(job.city ?? "");
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);

  const startEditing = () => {
    setTitle(job.title);
    setCompany(job.company_name);
    setCity(job.city ?? "");
    setFailed(false);
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setFailed(false);
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!title.trim()) {
      return;
    }

    const changes: JobChanges = {
      title: title.trim(),
      company_name: company.trim(),
    };
    // An empty city means "clear it", not "leave it".
    if (city.trim() !== (job.city ?? "")) {
      changes.city = city.trim() === "" ? null : city.trim();
    }

    setSaving(true);
    setFailed(false);
    try {
      await updateJob(job.id, changes);
      setEditing(false);
      onChanged();
    } catch {
      setFailed(true);
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <li className="rounded-lg border border-neutral-400 bg-white p-4">
        <form className="space-y-2" onSubmit={save}>
          <input
            className="w-full rounded border border-neutral-300 px-2 py-1 text-sm"
            onChange={(event) => setTitle(event.target.value)}
            value={title}
          />
          <div className="flex gap-2">
            <input
              className="w-full rounded border border-neutral-300 px-2 py-1 text-sm"
              onChange={(event) => setCompany(event.target.value)}
              placeholder={t("job.company")}
              value={company}
            />
            <input
              className="w-32 rounded border border-neutral-300 px-2 py-1 text-sm"
              onChange={(event) => setCity(event.target.value)}
              placeholder={t("job.city")}
              value={city}
            />
          </div>
          <div className="flex items-center gap-3">
            <button
              className="rounded bg-neutral-900 px-3 py-1 text-xs text-white disabled:opacity-40"
              disabled={saving || !title.trim()}
              type="submit"
            >
              {saving ? t("job.saving") : t("job.save")}
            </button>
            <button
              className="text-xs text-neutral-500 hover:text-neutral-800"
              onClick={cancel}
              type="button"
            >
              {t("job.cancel")}
            </button>
            {failed ? <span className="text-xs text-red-700">{t("job.error")}</span> : null}
          </div>
        </form>
      </li>
    );
  }

  const meta = [job.company_name, job.city, job.salary_text].filter(Boolean).join(" · ");

  return (
    <li className="rounded-lg border border-neutral-200 bg-white p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="truncate font-medium">{job.title}</h2>
          <p className="mt-1 text-sm text-neutral-600">{meta}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-600">
            {job.platform}
          </span>
          <button
            className="text-xs text-neutral-500 hover:text-neutral-900"
            onClick={startEditing}
            type="button"
          >
            {t("job.edit")}
          </button>
        </div>
      </div>
      {job.snippet ? (
        <p className="mt-2 text-xs leading-relaxed text-neutral-500">
          <Snippet text={job.snippet} />
        </p>
      ) : null}
    </li>
  );
}
