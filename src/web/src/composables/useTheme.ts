import { computed, ref, watchEffect } from "vue";
import { darkTheme, lightTheme } from "naive-ui";
import { useAccent } from "@/composables/useAccent";
import { cssVarsFor } from "@/styles/theme";

export type ThemeMode = "light" | "dark" | "system";

const STORAGE_KEY = "or-theme";

function loadMode(): ThemeMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    /* private mode */
  }
  return "system";
}

const mode = ref<ThemeMode>(loadMode());
const systemDark = ref(
  typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches,
);

if (typeof window !== "undefined") {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", (e) => {
    systemDark.value = e.matches;
  });
}

const isDark = computed(() => mode.value === "dark" || (mode.value === "system" && systemDark.value));

let applied = false;

export const themeModeOptions: { value: ThemeMode; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

export function useTheme() {
  const { overridesFor, accentId, preset, setAccent, accentOptions } = useAccent();
  const naiveTheme = computed(() => (isDark.value ? darkTheme : lightTheme));
  const overrides = computed(() => overridesFor(isDark.value));

  if (!applied && typeof document !== "undefined") {
    applied = true;
    watchEffect(() => {
      const root = document.documentElement;
      const dark = isDark.value;
      root.dataset.theme = dark ? "dark" : "light";
      root.style.colorScheme = dark ? "dark" : "light";
      const vars = cssVarsFor(accentId.value, dark);
      for (const [key, value] of Object.entries(vars)) {
        root.style.setProperty(key, value);
      }
      const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
      if (meta) meta.content = vars["--or-bg"];
      try {
        localStorage.setItem(STORAGE_KEY, mode.value);
      } catch {
        /* ignore */
      }
    });
  }

  function toggle() {
    mode.value = isDark.value ? "light" : "dark";
  }

  function setTheme(value: ThemeMode) {
    mode.value = value;
  }

  return {
    mode,
    isDark,
    naiveTheme,
    overrides,
    toggle,
    setTheme,
    themeModeOptions,
    accentId,
    preset,
    setAccent,
    accentOptions,
  };
}
