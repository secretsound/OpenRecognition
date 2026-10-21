import { computed, ref, watch } from "vue";
import { darkTheme, lightTheme } from "naive-ui";
import { useAccent } from "@/composables/useAccent";

const STORAGE_KEY = "or-theme";

function loadTheme(): "light" | "dark" {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

const mode = ref<"light" | "dark">(loadTheme());

export function useTheme() {
  const { overridesFor, accentId, preset, setAccent, accentOptions } = useAccent();
  const isDark = computed(() => mode.value === "dark");
  const naiveTheme = computed(() => (isDark.value ? darkTheme : lightTheme));
  const overrides = computed(() => overridesFor(isDark.value));

  function toggle() {
    mode.value = mode.value === "light" ? "dark" : "light";
  }

  function setTheme(value: "light" | "dark") {
    mode.value = value;
  }

  watch(mode, (v) => localStorage.setItem(STORAGE_KEY, v), { immediate: true });

  return {
    mode,
    isDark,
    naiveTheme,
    overrides,
    toggle,
    setTheme,
    accentId,
    preset,
    setAccent,
    accentOptions,
  };
}
