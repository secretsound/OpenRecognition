<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: number;
    title?: string;
    /** Inverted: light tile with accent glyph, for accent or dark backgrounds. */
    variant?: "default" | "inverted";
  }>(),
  { size: 32, title: "OpenRecognition", variant: "default" },
);
</script>

<template>
  <svg
    class="logo-mark"
    :class="`logo-mark--${variant}`"
    :width="size"
    :height="size"
    :aria-label="title"
    role="img"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 32 32"
    fill="none"
  >
    <rect width="32" height="32" rx="8" class="logo-mark__tile" />
    <circle cx="16" cy="14" r="6" class="logo-mark__stroke" stroke-width="2" />
    <path
      d="M8 26c2-4 6-6 8-6s6 2 8 6"
      class="logo-mark__stroke"
      stroke-width="2"
      stroke-linecap="round"
    />
  </svg>
</template>

<style scoped>
.logo-mark {
  flex-shrink: 0;
  display: block;
}

.logo-mark__tile {
  fill: var(--or-accent);
}

.logo-mark__stroke {
  stroke: var(--or-on-accent);
}

.logo-mark--inverted .logo-mark__tile {
  fill: rgba(255, 255, 255, 0.95);
}

.logo-mark--inverted .logo-mark__stroke {
  stroke: var(--or-accent);
}
</style>
