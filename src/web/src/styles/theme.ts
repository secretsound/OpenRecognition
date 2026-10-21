import type { GlobalThemeOverrides } from "naive-ui";

export interface AccentPreset {
  id: string;
  label: string;
  primary: string;
  hover: string;
  pressed: string;
  suppl: string;
  gradientEnd: string;
}

export const accentPresets = {
  forest: {
    id: "forest",
    label: "Forest",
    primary: "#18a058",
    hover: "#36ad6a",
    pressed: "#0c7a43",
    suppl: "#36ad6a",
    gradientEnd: "#0c7a43",
  },
  ocean: {
    id: "ocean",
    label: "Ocean",
    primary: "#0891b2",
    hover: "#22b8cf",
    pressed: "#0e7490",
    suppl: "#22b8cf",
    gradientEnd: "#0e7490",
  },
  violet: {
    id: "violet",
    label: "Violet",
    primary: "#7c3aed",
    hover: "#8b5cf6",
    pressed: "#6d28d9",
    suppl: "#8b5cf6",
    gradientEnd: "#6d28d9",
  },
  indigo: {
    id: "indigo",
    label: "Indigo",
    primary: "#4f46e5",
    hover: "#6366f1",
    pressed: "#4338ca",
    suppl: "#818cf8",
    gradientEnd: "#3730a3",
  },
  rose: {
    id: "rose",
    label: "Rose",
    primary: "#e11d48",
    hover: "#f43f5e",
    pressed: "#be123c",
    suppl: "#fb7185",
    gradientEnd: "#9f1239",
  },
  amber: {
    id: "amber",
    label: "Amber",
    primary: "#d97706",
    hover: "#f59e0b",
    pressed: "#b45309",
    suppl: "#fbbf24",
    gradientEnd: "#92400e",
  },
  sunset: {
    id: "sunset",
    label: "Sunset",
    primary: "#ea580c",
    hover: "#f97316",
    pressed: "#c2410c",
    suppl: "#fb923c",
    gradientEnd: "#9a3412",
  },
  mint: {
    id: "mint",
    label: "Mint",
    primary: "#14b8a6",
    hover: "#2dd4bf",
    pressed: "#0d9488",
    suppl: "#5eead4",
    gradientEnd: "#0f766e",
  },
  steel: {
    id: "steel",
    label: "Steel",
    primary: "#5b6b8c",
    hover: "#7085a8",
    pressed: "#46566f",
    suppl: "#8b9cb8",
    gradientEnd: "#3d4a5c",
  },
} as const satisfies Record<string, AccentPreset>;

export type AccentPresetId = keyof typeof accentPresets;

export const defaultAccentId: AccentPresetId = "forest";

export function isAccentPresetId(value: string | null): value is AccentPresetId {
  return value != null && value in accentPresets;
}

const baseOverrides: GlobalThemeOverrides = {
  common: {
    borderRadius: "10px",
    fontFamily: "Inter, system-ui, -apple-system, sans-serif",
    infoColor: "#2080f0",
    infoColorHover: "#4098fc",
    infoColorPressed: "#1060c9",
    warningColor: "#f0a020",
    warningColorHover: "#fcb040",
    warningColorPressed: "#c97c10",
  },
  Card: {
    borderRadius: "12px",
    color: "#ffffff",
    borderColor: "rgba(15, 23, 42, 0.08)",
  },
  Button: {
    borderRadiusMedium: "8px",
    borderRadiusSmall: "8px",
  },
  Layout: {
    color: "#f4f5f7",
    siderColor: "#ffffff",
    headerColor: "#ffffff",
  },
  DataTable: {
    borderRadius: "12px",
  },
};

export const themeOverridesDark: GlobalThemeOverrides = {
  Card: {
    color: "#17181c",
    borderColor: "rgba(255, 255, 255, 0.08)",
  },
  Layout: {
    color: "#0e0f12",
    siderColor: "#14161a",
    headerColor: "#14161a",
  },
};

export function buildThemeOverrides(
  accentId: AccentPresetId = defaultAccentId,
  isDark = false,
): GlobalThemeOverrides {
  const accent = accentPresets[accentId];
  const merged: GlobalThemeOverrides = {
    ...baseOverrides,
    common: {
      ...baseOverrides.common,
      primaryColor: accent.primary,
      primaryColorHover: accent.hover,
      primaryColorPressed: accent.pressed,
      primaryColorSuppl: accent.suppl,
    },
  };
  if (isDark) {
    return {
      ...merged,
      Card: { ...merged.Card, ...themeOverridesDark.Card },
      Layout: { ...merged.Layout, ...themeOverridesDark.Layout },
    };
  }
  return merged;
}

/** @deprecated Use buildThemeOverrides via useTheme */
export const themeOverrides = buildThemeOverrides(defaultAccentId, false);
