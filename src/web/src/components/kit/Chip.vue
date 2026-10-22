<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: "default" | "success" | "warning" | "error" | "info" | "accent" | "audio" | "image" | "video";
    size?: "sm" | "md";
  }>(),
  { tone: "default", size: "sm" },
);
</script>

<template>
  <span class="or-chip" :class="[`or-chip--${tone}`, `or-chip--${size}`]">
    <slot />
  </span>
</template>
