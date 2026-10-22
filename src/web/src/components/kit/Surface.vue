<script setup lang="ts">
withDefaults(
  defineProps<{
    padding?: "none" | "sm" | "md" | "lg";
    tone?: "default" | "sunken" | "raised";
    interactive?: boolean;
  }>(),
  { padding: "md", tone: "default" },
);
</script>

<template>
  <div
    class="or-surface"
    :class="[
      `or-surface--${padding}`,
      `or-surface--${tone}`,
      { 'or-surface--interactive': interactive },
    ]"
  >
    <slot />
  </div>
</template>
