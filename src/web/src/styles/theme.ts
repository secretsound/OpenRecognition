import type { GlobalThemeOverrides } from "naive-ui";
import { accentStates, alpha } from "@/utils/color";

/* -------------------------------------------------------------------------- */
/*  Accents                                                                   */
/* -------------------------------------------------------------------------- */

export interface AccentPreset {
  id: string;
  label: string;
  primary: string;
}

export const accentPresets = {
  forest: { id: "forest", label: "Forest", primary: "#1f9d55" },
  ocean: { id: "ocean", label: "Ocean", primary: "#0e8fb3" },
  violet: { id: "violet", label: "Violet", primary: "#7c3aed" },
  indigo: { id: "indigo", label: "Indigo", primary: "#4f46e5" },
  rose: { id: "rose", label: "Rose", primary: "#e11d48" },
  amber: { id: "amber", label: "Amber", primary: "#d97706" },
  sunset: { id: "sunset", label: "Sunset", primary: "#ea580c" },
  mint: { id: "mint", label: "Mint", primary: "#14a394" },
  steel: { id: "steel", label: "Steel", primary: "#5b6b8c" },
} as const satisfies Record<string, AccentPreset>;

export type AccentPresetId = keyof typeof accentPresets;

export const defaultAccentId: AccentPresetId = "forest";

export function isAccentPresetId(value: string | null): value is AccentPresetId {
  return value != null && value in accentPresets;
}

/* -------------------------------------------------------------------------- */
/*  Neutral palettes (warm). Single source for CSS vars and Naive overrides.  */
/* -------------------------------------------------------------------------- */

export interface Palette {
  bg: string;
  surface: string;
  raised: string;
  sunken: string;
  line: string;
  lineStrong: string;
  text1: string;
  text2: string;
  text3: string;
  placeholder: string;
  hover: string;
  shadow: string;
  shadowRaised: string;
  success: string;
  warning: string;
  error: string;
  info: string;
}

export const palettes: Record<"light" | "dark", Palette> = {
  light: {
    bg: "#f5f4f1",
    surface: "#ffffff",
    raised: "#ffffff",
    sunken: "#edebe7",
    line: "rgba(28, 25, 23, 0.09)",
    lineStrong: "rgba(28, 25, 23, 0.18)",
    text1: "#1c1917",
    text2: "#57534e",
    text3: "#8a847d",
    placeholder: "#a8a29e",
    hover: "rgba(28, 25, 23, 0.045)",
    shadow: "0 1px 2px rgba(28, 25, 23, 0.06)",
    shadowRaised: "0 8px 24px rgba(28, 25, 23, 0.12), 0 2px 6px rgba(28, 25, 23, 0.06)",
    success: "#1f9d55",
    warning: "#d97706",
    error: "#dc2626",
    info: "#2563eb",
  },
  dark: {
    bg: "#121110",
    surface: "#1b1a18",
    raised: "#242220",
    sunken: "#0d0c0b",
    line: "rgba(245, 242, 238, 0.09)",
    lineStrong: "rgba(245, 242, 238, 0.18)",
    text1: "#f2efea",
    text2: "#b8b2aa",
    text3: "#857e76",
    placeholder: "#6b655e",
    hover: "rgba(245, 242, 238, 0.055)",
    shadow: "0 1px 2px rgba(0, 0, 0, 0.4)",
    shadowRaised: "0 12px 32px rgba(0, 0, 0, 0.5), 0 2px 6px rgba(0, 0, 0, 0.3)",
    success: "#34c072",
    warning: "#f0a530",
    error: "#ef5350",
    info: "#5b8def",
  },
};

/** Modality hues: the only non-semantic colors in the UI. Theme independent. */
export const modalityHues = {
  audio: "#14a394",
  image: "#7c5cff",
  video: "#e39a1c",
} as const;

export const fontStack =
  '"Inter Variable", Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
export const monoStack =
  'ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace';

/* -------------------------------------------------------------------------- */
/*  CSS variables                                                             */
/* -------------------------------------------------------------------------- */

export function cssVarsFor(accentId: AccentPresetId, dark: boolean): Record<string, string> {
  const p = palettes[dark ? "dark" : "light"];
  const a = accentStates(accentPresets[accentId].primary, dark);
  return {
    "--or-bg": p.bg,
    "--or-surface": p.surface,
    "--or-surface-raised": p.raised,
    "--or-surface-sunken": p.sunken,
    "--or-line": p.line,
    "--or-line-strong": p.lineStrong,
    "--or-text-1": p.text1,
    "--or-text-2": p.text2,
    "--or-text-3": p.text3,
    "--or-placeholder": p.placeholder,
    "--or-hover": p.hover,
    "--or-shadow": p.shadow,
    "--or-shadow-raised": p.shadowRaised,
    "--or-success": p.success,
    "--or-warning": p.warning,
    "--or-error": p.error,
    "--or-info": p.info,
    "--or-accent": a.base,
    "--or-accent-hover": a.hover,
    "--or-accent-pressed": a.pressed,
    "--or-on-accent": "#ffffff",
    "--or-audio": modalityHues.audio,
    "--or-image": modalityHues.image,
    "--or-video": modalityHues.video,
  };
}

/* -------------------------------------------------------------------------- */
/*  Naive UI overrides                                                        */
/* -------------------------------------------------------------------------- */

export function buildThemeOverrides(
  accentId: AccentPresetId = defaultAccentId,
  isDark = false,
): GlobalThemeOverrides {
  const p = palettes[isDark ? "dark" : "light"];
  const accent = accentStates(accentPresets[accentId].primary, isDark);
  const success = accentStates(p.success, isDark);
  const warning = accentStates(p.warning, isDark);
  const error = accentStates(p.error, isDark);
  const info = accentStates(p.info, isDark);

  return {
    common: {
      fontFamily: fontStack,
      fontFamilyMono: monoStack,
      fontSize: "14px",
      fontSizeTiny: "12px",
      fontSizeSmall: "13px",
      fontSizeMedium: "14px",
      fontSizeLarge: "15px",
      fontSizeHuge: "16px",
      fontWeight: "400",
      fontWeightStrong: "600",
      lineHeight: "1.5",
      borderRadius: "8px",
      borderRadiusSmall: "6px",
      heightTiny: "24px",
      heightSmall: "30px",
      heightMedium: "36px",
      heightLarge: "42px",
      heightHuge: "48px",
      cubicBezierEaseInOut: "cubic-bezier(0.2, 0, 0, 1)",
      cubicBezierEaseOut: "cubic-bezier(0, 0, 0.2, 1)",
      cubicBezierEaseIn: "cubic-bezier(0.4, 0, 1, 1)",

      primaryColor: accent.base,
      primaryColorHover: accent.hover,
      primaryColorPressed: accent.pressed,
      primaryColorSuppl: accent.suppl,
      successColor: success.base,
      successColorHover: success.hover,
      successColorPressed: success.pressed,
      successColorSuppl: success.suppl,
      warningColor: warning.base,
      warningColorHover: warning.hover,
      warningColorPressed: warning.pressed,
      warningColorSuppl: warning.suppl,
      errorColor: error.base,
      errorColorHover: error.hover,
      errorColorPressed: error.pressed,
      errorColorSuppl: error.suppl,
      infoColor: info.base,
      infoColorHover: info.hover,
      infoColorPressed: info.pressed,
      infoColorSuppl: info.suppl,

      baseColor: isDark ? "#000000" : "#ffffff",
      bodyColor: p.bg,
      cardColor: p.surface,
      modalColor: p.raised,
      popoverColor: p.raised,
      tableColor: p.surface,
      tableHeaderColor: p.sunken,
      tableColorHover: p.hover,
      tableColorStriped: p.sunken,
      inputColor: p.surface,
      inputColorDisabled: p.sunken,
      actionColor: p.sunken,
      hoverColor: p.hover,
      pressedColor: alpha(p.text1, isDark ? 0.1 : 0.08),
      tagColor: p.sunken,
      codeColor: p.sunken,
      buttonColor2: alpha(p.text1, 0.06),
      buttonColor2Hover: alpha(p.text1, 0.09),
      buttonColor2Pressed: alpha(p.text1, 0.12),
      avatarColor: p.sunken,
      railColor: alpha(p.text1, isDark ? 0.22 : 0.16),
      progressRailColor: alpha(p.text1, isDark ? 0.14 : 0.08),
      borderColor: p.line,
      dividerColor: p.line,
      closeColorHover: p.hover,
      closeColorPressed: alpha(p.text1, 0.1),
      textColorBase: p.text1,
      textColor1: p.text1,
      textColor2: p.text2,
      textColor3: p.text3,
      textColorDisabled: p.placeholder,
      placeholderColor: p.placeholder,
      placeholderColorDisabled: alpha(p.placeholder, 0.6),
      iconColor: p.text3,
      iconColorHover: p.text2,
      iconColorPressed: p.text1,
      iconColorDisabled: p.placeholder,
      closeIconColor: p.text3,
      closeIconColorHover: p.text1,
      closeIconColorPressed: p.text1,
      clearColor: p.text3,
      clearColorHover: p.text2,
      scrollbarColor: alpha(p.text1, 0.2),
      scrollbarColorHover: alpha(p.text1, 0.32),
      boxShadow1: p.shadow,
      boxShadow2: p.shadowRaised,
      boxShadow3: p.shadowRaised,
    },
    Layout: {
      color: p.bg,
      siderColor: p.surface,
      headerColor: p.surface,
      footerColor: p.surface,
      siderBorderColor: p.line,
      headerBorderColor: p.line,
      textColor: p.text1,
    },
    Card: {
      color: p.surface,
      colorModal: p.raised,
      colorPopover: p.raised,
      borderColor: p.line,
      borderRadius: "14px",
      paddingSmall: "16px 18px",
      paddingMedium: "20px 24px",
      paddingLarge: "24px 28px",
      titleFontSizeSmall: "15px",
      titleFontSizeMedium: "16px",
      titleFontSizeLarge: "18px",
      titleFontWeight: "600",
      actionColor: p.sunken,
    },
    Button: {
      borderRadiusTiny: "6px",
      borderRadiusSmall: "8px",
      borderRadiusMedium: "8px",
      borderRadiusLarge: "10px",
      fontWeight: "500",
      fontWeightStrong: "600",
      paddingMedium: "0 16px",
      paddingSmall: "0 12px",
    },
    Input: {
      borderRadius: "8px",
      color: p.surface,
      colorFocus: p.surface,
      border: `1px solid ${p.lineStrong}`,
      borderHover: `1px solid ${accent.hover}`,
      borderFocus: `1px solid ${accent.base}`,
      boxShadowFocus: `0 0 0 3px ${alpha(accent.base, 0.18)}`,
    },
    InternalSelection: {
      borderRadius: "8px",
      color: p.surface,
      border: `1px solid ${p.lineStrong}`,
      borderHover: `1px solid ${accent.hover}`,
      borderFocus: `1px solid ${accent.base}`,
      borderActive: `1px solid ${accent.base}`,
      boxShadowFocus: `0 0 0 3px ${alpha(accent.base, 0.18)}`,
      boxShadowActive: `0 0 0 3px ${alpha(accent.base, 0.18)}`,
    },
    InternalSelectMenu: {
      borderRadius: "10px",
      color: p.raised,
      optionHeightMedium: "34px",
    },
    DataTable: {
      borderRadius: "12px",
      borderColor: p.line,
      thColor: p.sunken,
      thColorHover: p.sunken,
      thTextColor: p.text2,
      thFontWeight: "600",
      tdColor: p.surface,
      tdColorHover: p.hover,
      tdTextColor: p.text1,
      thPaddingMedium: "10px 14px",
      tdPaddingMedium: "12px 14px",
      thPaddingSmall: "8px 12px",
      tdPaddingSmall: "9px 12px",
      fontSizeMedium: "14px",
      lineHeight: "1.45",
    },
    Menu: {
      itemHeight: "36px",
      borderRadius: "8px",
      fontSize: "14px",
      itemTextColor: p.text2,
      itemTextColorHover: p.text1,
      itemTextColorActive: accent.base,
      itemTextColorActiveHover: accent.base,
      itemTextColorChildActive: accent.base,
      itemIconColor: p.text3,
      itemIconColorHover: p.text1,
      itemIconColorActive: accent.base,
      itemIconColorActiveHover: accent.base,
      itemColorHover: p.hover,
      itemColorActive: alpha(accent.base, isDark ? 0.18 : 0.1),
      itemColorActiveHover: alpha(accent.base, isDark ? 0.22 : 0.14),
      itemColorActiveCollapsed: alpha(accent.base, isDark ? 0.18 : 0.1),
      groupTextColor: p.text3,
      arrowColor: p.text3,
      dividerColor: p.line,
    },
    Tag: {
      borderRadius: "999px",
      color: p.sunken,
      textColor: p.text2,
      fontWeightStrong: "600",
      padding: "0 9px",
      heightSmall: "22px",
      heightMedium: "26px",
    },
    Tabs: {
      tabFontSizeMedium: "14px",
      tabFontWeightActive: "600",
      tabTextColorLine: p.text2,
      tabTextColorActiveLine: p.text1,
      tabTextColorHoverLine: p.text1,
      barColor: accent.base,
      tabPaddingMediumLine: "10px 0",
      tabGapMediumLine: "24px",
      tabBorderColor: p.line,
      tabColorSegment: p.surface,
      tabTextColorSegment: p.text2,
      tabTextColorActiveSegment: p.text1,
      tabTextColorHoverSegment: p.text1,
      colorSegment: p.sunken,
      tabBorderRadius: "8px",
    },
    Alert: {
      borderRadius: "10px",
      padding: "12px 14px",
      titleFontWeight: "600",
      fontSize: "14px",
    },
    Dialog: {
      borderRadius: "14px",
      color: p.raised,
      padding: "24px",
      titleFontSize: "17px",
      fontSize: "14px",
    },
    Modal: {
      color: p.raised,
    },
    Drawer: {
      color: p.raised,
      headerPadding: "18px 24px",
      bodyPadding: "20px 24px",
      footerPadding: "16px 24px",
      titleFontSize: "17px",
      titleFontWeight: "600",
    },
    Popover: {
      color: p.raised,
      borderRadius: "10px",
      padding: "10px 12px",
      fontSize: "13px",
    },
    Tooltip: {
      color: isDark ? p.raised : "#1c1917",
      textColor: isDark ? p.text1 : "#ffffff",
      borderRadius: "8px",
      padding: "6px 10px",
      boxShadow: p.shadowRaised,
    },
    Dropdown: {
      color: p.raised,
      borderRadius: "10px",
      optionHeightMedium: "34px",
      padding: "6px",
      optionColorHover: p.hover,
      optionTextColor: p.text1,
      optionIconSizeMedium: "16px",
      dividerColor: p.line,
    },
    Switch: {
      railColor: alpha(p.text1, isDark ? 0.22 : 0.16),
      railColorActive: accent.base,
      railHeightMedium: "22px",
      railWidthMedium: "40px",
      buttonHeightMedium: "18px",
      buttonWidthMedium: "18px",
      buttonWidthPressedMedium: "22px",
    },
    Slider: {
      railHeight: "4px",
      railColor: alpha(p.text1, isDark ? 0.22 : 0.14),
      railColorHover: alpha(p.text1, isDark ? 0.28 : 0.18),
      fillColor: accent.base,
      fillColorHover: accent.hover,
      handleSize: "18px",
      handleColor: "#ffffff",
      handleBoxShadow: `0 0 0 1px ${p.lineStrong}, 0 1px 3px rgba(0,0,0,0.2)`,
      handleBoxShadowHover: `0 0 0 1px ${p.lineStrong}, 0 2px 6px rgba(0,0,0,0.25)`,
      handleBoxShadowActive: `0 0 0 3px ${alpha(accent.base, 0.25)}`,
      handleBoxShadowFocus: `0 0 0 3px ${alpha(accent.base, 0.25)}`,
      dotColor: p.surface,
    },
    Progress: {
      railColor: alpha(p.text1, isDark ? 0.14 : 0.08),
      railHeight: "6px",
      fillColor: accent.base,
    },
    Steps: {
      indicatorBorderColorFinish: accent.base,
      indicatorColorFinish: accent.base,
      indicatorBorderColorProcess: accent.base,
      indicatorColorProcess: accent.base,
      splitorColorFinish: accent.base,
      stepHeaderFontSizeSmall: "13px",
      stepHeaderFontSizeMedium: "14px",
    },
    Checkbox: {
      borderRadius: "5px",
      border: `1px solid ${p.lineStrong}`,
      colorChecked: accent.base,
      borderChecked: `1px solid ${accent.base}`,
      borderFocus: `1px solid ${accent.base}`,
      boxShadowFocus: `0 0 0 3px ${alpha(accent.base, 0.18)}`,
    },
    Radio: {
      dotColorActive: accent.base,
      boxShadowActive: `inset 0 0 0 1px ${accent.base}`,
      boxShadowFocus: `inset 0 0 0 1px ${accent.base}, 0 0 0 3px ${alpha(accent.base, 0.18)}`,
      boxShadowHover: `inset 0 0 0 1px ${accent.hover}`,
      buttonBorderColorActive: accent.base,
      buttonTextColorActive: accent.base,
      buttonBoxShadowFocus: `inset 0 0 0 1px ${accent.base}, 0 0 0 3px ${alpha(accent.base, 0.18)}`,
    },
    Skeleton: {
      color: alpha(p.text1, isDark ? 0.08 : 0.06),
      colorEnd: alpha(p.text1, isDark ? 0.14 : 0.1),
      borderRadius: "8px",
    },
    Upload: {
      draggerColor: p.sunken,
      draggerBorder: `1px dashed ${p.lineStrong}`,
      draggerBorderHover: `1px dashed ${accent.base}`,
      itemColorHover: p.hover,
      itemBorderImageCard: `1px solid ${p.line}`,
    },
    Pagination: {
      itemBorderRadius: "8px",
      itemColorActive: alpha(accent.base, isDark ? 0.18 : 0.1),
      itemTextColorActive: accent.base,
      itemBorderActive: "1px solid transparent",
      itemBorder: "1px solid transparent",
      itemColorHover: p.hover,
      buttonBorder: "1px solid transparent",
      buttonBorderHover: "1px solid transparent",
      buttonColor: "transparent",
      buttonColorHover: p.hover,
    },
    Empty: {
      textColor: p.text2,
      iconColor: p.text3,
    },
    Descriptions: {
      thColor: p.sunken,
      thTextColor: p.text2,
      tdTextColor: p.text1,
      thFontWeight: "500",
      borderRadius: "10px",
    },
    Message: {
      borderRadius: "10px",
      color: p.raised,
      textColor: p.text1,
      boxShadow: p.shadowRaised,
      padding: "10px 14px",
      colorInfo: p.raised,
      colorSuccess: p.raised,
      colorWarning: p.raised,
      colorError: p.raised,
      textColorInfo: p.text1,
      textColorSuccess: p.text1,
      textColorWarning: p.text1,
      textColorError: p.text1,
    },
    Notification: {
      borderRadius: "12px",
      color: p.raised,
      boxShadow: p.shadowRaised,
      titleFontSize: "15px",
      padding: "16px 18px",
    },
    Collapse: {
      titleFontWeight: "600",
      titleFontSize: "14px",
      dividerColor: p.line,
      itemMargin: "12px 0 0 0",
      titlePadding: "12px 0 0 0",
    },
    Code: {
      fontSize: "13px",
      color: p.sunken,
      textColor: p.text1,
    },
    Statistic: {
      labelFontSize: "13px",
      valueFontSize: "28px",
      valueFontWeight: "600",
      labelTextColor: p.text3,
    },
    Breadcrumb: {
      fontSize: "13px",
      itemTextColor: p.text3,
      itemTextColorHover: p.text1,
      itemTextColorPressed: p.text1,
      itemTextColorActive: p.text1,
      separatorColor: p.text3,
      itemColorHover: "transparent",
      itemColorPressed: "transparent",
    },
    Avatar: {
      color: p.sunken,
      borderRadius: "999px",
    },
    Badge: {
      color: error.base,
    },
    Divider: {
      color: p.line,
    },
  };
}
