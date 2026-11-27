import { useEffect, useState } from "react";

import { t } from "../i18n";

type Health = "checking" | "ok" | "unreachable";

const dotClass: Record<Health, string> = {
  checking: "bg-neutral-300",
  ok: "bg-emerald-500",
  unreachable: "bg-red-500",
};

export default function Dashboard() {
  const [health, setHealth] = useState<Health>("checking");

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

  return (
    <section className="space-y-8">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">{t("dashboard.title")}</h1>
        <span className="flex items-center gap-2 text-xs text-neutral-500">
          <span className={`size-2 rounded-full ${dotClass[health]}`} aria-hidden="true" />
          {t("health.label")}：{t(`health.${health}`)}
        </span>
      </div>

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

      <p className="text-xs text-neutral-400">{t("status.milestone", { value: "M0" })}</p>
    </section>
  );
}
