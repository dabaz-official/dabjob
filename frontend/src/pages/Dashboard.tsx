import { type FormEvent, useEffect, useState } from "react";

import { type JobSummary, fetchJobs } from "../api";
import PastePanel from "../components/PastePanel";
import { t } from "../i18n";

type Health = "checking" | "ok" | "unreachable";
type LoadState = "loading" | "ready" | "error";

const dotClass: Record<Health, string> = {
  checking: "bg-neutral-300",
  ok: "bg-emerald-500",
  unreachable: "bg-red-500",
};

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

function JobCard({ job }: { job: JobSummary }) {
  const meta = [job.company_name, job.city, job.salary_text].filter(Boolean).join(" · ");

  return (
    <li className="rounded-lg border border-neutral-200 bg-white p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="truncate font-medium">{job.title}</h2>
          <p className="mt-1 text-sm text-neutral-600">{meta}</p>
        </div>
        <span className="shrink-0 rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-600">
          {job.platform}
        </span>
      </div>
      {job.snippet ? (
        <p className="mt-2 text-xs leading-relaxed text-neutral-500">
          <Snippet text={job.snippet} />
        </p>
      ) : null}
    </li>
  );
}

export default function Dashboard() {
  const [health, setHealth] = useState<Health>("checking");
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState<LoadState>("loading");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    fetch("/api/health")
      .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
      .then((body: { ok?: boolean }) => {
        if (!cancelled) {
          setHealth(body.ok === true ? "ok" : "unreachable");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHealth("unreachable");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setState("loading");

    fetchJobs(submitted)
      .then((list) => {
        if (!cancelled) {
          setJobs(list.items);
          setTotal(list.total);
          setState("ready");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState("error");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [submitted, reloadKey]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(query.trim());
  };

  const onClear = () => {
    setQuery("");
    setSubmitted("");
  };

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">{t("dashboard.title")}</h1>
        <span className="flex items-center gap-2 text-xs text-neutral-500">
          <span className={`size-2 rounded-full ${dotClass[health]}`} aria-hidden="true" />
          {t("health.label")}：{t(`health.${health}`)}
        </span>
      </div>

      <PastePanel onImported={() => setReloadKey((value) => value + 1)} />

      <form className="flex gap-2" onSubmit={onSubmit}>
        <input
          className="w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm outline-none focus:border-neutral-500"
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("dashboard.search.placeholder")}
          type="search"
          value={query}
        />
        <button
          className="shrink-0 rounded-lg bg-neutral-900 px-4 py-2 text-sm text-white hover:bg-neutral-700"
          type="submit"
        >
          {t("dashboard.search.action")}
        </button>
        {submitted ? (
          <button
            className="shrink-0 rounded-lg px-3 py-2 text-sm text-neutral-600 hover:text-neutral-900"
            onClick={onClear}
            type="button"
          >
            {t("dashboard.search.clear")}
          </button>
        ) : null}
      </form>

      {state === "loading" ? (
        <p className="text-sm text-neutral-500">{t("dashboard.loading")}</p>
      ) : null}

      {state === "error" ? (
        <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {t("dashboard.error")}
        </p>
      ) : null}

      {state === "ready" ? (
        <>
          <p className="text-xs text-neutral-500">{t("dashboard.count", { count: total })}</p>

          {total === 0 ? (
            submitted ? (
              <p className="rounded-xl border border-dashed border-neutral-300 bg-white p-10 text-center text-sm text-neutral-600">
                {t("dashboard.noResults", { query: submitted })}
              </p>
            ) : (
              <div className="rounded-xl border border-dashed border-neutral-300 bg-white p-10 text-center">
                <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">
                  {t("dashboard.empty.badge")}
                </p>
                <h2 className="mt-3 text-lg font-medium">{t("dashboard.empty.title")}</h2>
                <p className="mx-auto mt-2 max-w-md text-sm text-neutral-600">
                  {t("dashboard.empty.body")}
                </p>
                <p className="mt-4 text-xs text-neutral-400">{t("dashboard.empty.hint")}</p>
              </div>
            )
          ) : (
            <ul className="space-y-3">
              {jobs.map((job) => (
                <JobCard job={job} key={job.id} />
              ))}
            </ul>
          )}
        </>
      ) : null}

      <p className="text-xs text-neutral-400">{t("status.milestone", { value: "M1" })}</p>
    </section>
  );
}
