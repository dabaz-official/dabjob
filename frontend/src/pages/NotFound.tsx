import { Link } from "react-router-dom";

import { t } from "../i18n";

export default function NotFound() {
  return (
    <section className="space-y-4 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">{t("notFound.title")}</h1>
      <p className="text-sm text-neutral-600">{t("notFound.body")}</p>
      <Link className="text-sm underline underline-offset-4" to="/">
        {t("notFound.action")}
      </Link>
    </section>
  );
}
