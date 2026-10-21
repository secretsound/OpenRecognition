<script setup lang="ts">
import { computed } from "vue";
import { useAccent } from "@/composables/useAccent";

const props = withDefaults(
  defineProps<{
    size?: number;
    title?: string;
    /** White tile + primary icon — for accent gradient panels (login). */
    variant?: "default" | "on-dark";
  }>(),
  { size: 32, title: "OpenRecognition", variant: "default" },
);

const { preset } = useAccent();

const bgFill = computed(() =>
  props.variant === "on-dark" ? "rgba(255, 255, 255, 0.95)" : preset.value.primary,
);

const iconColor = computed(() =>
  props.variant === "on-dark" ? preset.value.primary : "#ffffff",
);
</script>

<template>
  <svg
    class="logo-mark"
    :width="size"
    :height="size"
    :aria-label="title"
    role="img"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 32 32"
    fill="none"
  >
    <rect width="32" height="32" rx="8" :fill="bgFill" />
    <circle cx="16" cy="14" r="6" :stroke="iconColor" stroke-width="2" />
    <path
      d="M8 26c2-4 6-6 8-6s6 2 8 6"
      :stroke="iconColor"
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
</style>
