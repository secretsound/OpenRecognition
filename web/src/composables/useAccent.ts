import { computed, ref, watch } from "vue";
import {
  accentPresets,
  buildThemeOverrides,
  defaultAccentId,
  isAccentPresetId,
  type AccentPresetId,
} from "@/styles/theme";

const STORAGE_KEY = "or-accent";

function loadAccent(): AccentPresetId {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (isAccentPresetId(stored)) return stored;
  return defaultAccentId;
}

const accentId = ref<AccentPresetId>(loadAccent());

export function useAccent() {
  const preset = computed(() => accentPresets[accentId.value]);

  const accentOptions = computed(() =>
    Object.values(accentPresets).map((p) => ({
      label: p.label,
      value: p.id,
    })),
  );

  function setAccent(id: AccentPresetId) {
    accentId.value = id;
  }

  function overridesFor(isDark: boolean) {
    return buildThemeOverrides(accentId.value, isDark);
  }

  watch(accentId, (v) => localStorage.setItem(STORAGE_KEY, v), { immediate: true });

  return {
    accentId,
    preset,
    accentOptions,
    setAccent,
    overridesFor,
    gradientEnd: computed(() => preset.value.gradientEnd),
  };
}
