import { computed, ref, watch } from "vue";
import {
  accentPresets,
  buildThemeOverrides,
  defaultAccentId,
  isAccentPresetId,
  type AccentPresetId,
} from "@/styles/theme";
import { t } from "@/i18n";

const STORAGE_KEY = "or-accent";

function loadAccent(): AccentPresetId {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isAccentPresetId(stored)) return stored;
  } catch {
    /* private mode */
  }
  return defaultAccentId;
}

const accentId = ref<AccentPresetId>(loadAccent());

watch(accentId, (v) => {
  try {
    localStorage.setItem(STORAGE_KEY, v);
  } catch {
    /* ignore */
  }
});

export function useAccent() {
  const preset = computed(() => accentPresets[accentId.value]);

  const accentOptions = computed(() =>
    Object.values(accentPresets).map((p) => ({
      label: t(`accent.${p.id}`),
      value: p.id as AccentPresetId,
      color: p.primary,
    })),
  );

  function setAccent(id: AccentPresetId) {
    accentId.value = id;
  }

  function overridesFor(isDark: boolean) {
    return buildThemeOverrides(accentId.value, isDark);
  }

  return {
    accentId,
    preset,
    accentOptions,
    setAccent,
    overridesFor,
  };
}
