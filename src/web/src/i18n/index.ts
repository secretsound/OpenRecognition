import { computed, ref } from "vue";
import {
  dateDeDE,
  dateEnUS,
  dateEsAR,
  dateFrFR,
  datePtBR,
  dateZhCN,
  deDE,
  enUS,
  esAR,
  frFR,
  ptBR,
  zhCN,
} from "naive-ui";
import { api } from "@/api/client";
import type { UiConfigOut } from "@/types/api";
import { catalogs } from "@/i18n/catalog";
import { setDisplayLocale, setDisplayTimeZone } from "@/utils/time";

export const LOCALES = ["en", "es", "fr", "de", "pt", "zh"] as const;
export type LocaleCode = (typeof LOCALES)[number];

export const locale = ref<LocaleCode>("en");
export const uiConfig = ref<UiConfigOut | null>(null);

const naiveLocales = { en: enUS, es: esAR, fr: frFR, de: deDE, pt: ptBR, zh: zhCN };
const naiveDates = {
  en: dateEnUS,
  es: dateEsAR,
  fr: dateFrFR,
  de: dateDeDE,
  pt: datePtBR,
  zh: dateZhCN,
};

export const naiveLocale = computed(() => naiveLocales[locale.value]);
export const naiveDateLocale = computed(() => naiveDates[locale.value]);

export function isLocale(value: string): value is LocaleCode {
  return (LOCALES as readonly string[]).includes(value);
}

export function setLocale(code: string) {
  locale.value = isLocale(code) ? code : "en";
  setDisplayLocale(locale.value);
}

export function t(key: string, vars?: Record<string, string | number>): string {
  const table = catalogs[locale.value] ?? catalogs.en;
  let text = table[key] ?? catalogs.en[key] ?? key;
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.replaceAll(`{${name}}`, String(value));
    }
  }
  return text;
}

const crumbKeys: Record<string, string> = {
  Home: "nav.overview",
  Library: "nav.library",
  New: "nav.new",
  Detail: "nav.detail",
  Recognize: "nav.recognize",
  Users: "nav.users",
  Groups: "nav.groups",
  "API keys": "nav.apiKeys",
  Connections: "nav.connections",
  Activity: "nav.activity",
  Models: "nav.models",
  Settings: "nav.settings",
};

export function crumbLabel(label: string): string {
  const key = crumbKeys[label];
  return key ? t(key) : label;
}

export function themeLabel(mode: string): string {
  if (mode === "light" || mode === "dark" || mode === "system") return t(`theme.${mode}`);
  return mode;
}

export function roleLabel(role: string | null | undefined): string {
  if (role === "admin" || role === "operator" || role === "viewer") return t(`role.${role}`);
  return t("role.signedIn");
}

export async function loadUiConfig() {
  const cfg = await api<UiConfigOut>("/v1/auth/ui", { skipAuthRedirect: true });
  uiConfig.value = cfg;
  setLocale(cfg.display_language);
  setDisplayTimeZone(cfg.display_timezone || "UTC");
  return cfg;
}
