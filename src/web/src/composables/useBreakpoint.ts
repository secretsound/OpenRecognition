import { computed, ref } from "vue";

/** Breakpoints shared with CSS: sm 640 · md 900 · lg 1200. */
export const BREAKPOINTS = { sm: 640, md: 900, lg: 1200 } as const;

const width = ref(typeof window !== "undefined" ? window.innerWidth : 1280);

if (typeof window !== "undefined") {
  let frame = 0;
  window.addEventListener(
    "resize",
    () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        width.value = window.innerWidth;
      });
    },
    { passive: true },
  );
}

export function useBreakpoint() {
  /** Under 640px: phones. */
  const isNarrow = computed(() => width.value < BREAKPOINTS.sm);
  /** Under 900px: phones and small tablets. Sidebar hides, tables become cards. */
  const isMobile = computed(() => width.value < BREAKPOINTS.md);
  /** 1200px and up: room for a secondary column. */
  const isWide = computed(() => width.value >= BREAKPOINTS.lg);
  return { width, isNarrow, isMobile, isWide };
}
