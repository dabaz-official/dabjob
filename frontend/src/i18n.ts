/**
 * Minimal i18n: a flat key map and a lookup.
 *
 * One locale ships (`zh-CN`), but no component may contain a user-facing
 * string. Retrofitting this later costs far more than doing it from the
 * first screen, which is why it exists before there are screens.
 */
import zhCN from "../locales/zh-CN.json";

const locales: Record<string, Record<string, string>> = { "zh-CN": zhCN };

let activeLocale = "zh-CN";

export function setLocale(locale: string): void {
  if (locales[locale]) {
    activeLocale = locale;
  }
}

export function availableLocales(): string[] {
  return Object.keys(locales);
}

export function t(key: string, vars?: Record<string, string | number>): string {
  const dict = locales[activeLocale] ?? {};
  let value = dict[key] ?? key;
  if (vars) {
    for (const [name, replacement] of Object.entries(vars)) {
      value = value.split(`{${name}}`).join(String(replacement));
    }
  }
  return value;
}
