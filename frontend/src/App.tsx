import { NavLink, Route, Routes } from "react-router-dom";

import { t } from "./i18n";
import Dashboard from "./pages/Dashboard";
import NotFound from "./pages/NotFound";

const navLinkClass = ({ isActive }: { isActive: boolean }): string =>
  isActive ? "text-neutral-900" : "text-neutral-500 hover:text-neutral-800";

export default function App() {
  return (
    <div className="min-h-screen bg-neutral-50 text-neutral-900">
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-baseline gap-6 px-6 py-4">
          <span className="text-lg font-semibold tracking-tight">{t("app.name")}</span>
          <span className="hidden text-sm text-neutral-500 sm:inline">{t("app.tagline")}</span>
          <nav className="ml-auto text-sm">
            <NavLink to="/" end className={navLinkClass}>
              {t("nav.dashboard")}
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-10">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}
