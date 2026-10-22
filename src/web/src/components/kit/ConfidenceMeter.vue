<script setup lang="ts">
import { computed } from "vue";
import { confidenceTone, pct } from "@/utils/confidence";

const props = withDefaults(
  defineProps<{
    value: number | null | undefined;
    threshold?: number | null;
    size?: "sm" | "md" | "lg";
    showLabel?: boolean;
  }>(),
  { size: "md", showLabel: true },
);

const tone = computed(() => confidenceTone(props.value, props.threshold));
const width = computed(() => {
  if (props.value == null || Number.isNaN(props.value)) return 0;
  return Math.max(0, Math.min(100, props.value * 100));
});
const tick = computed(() => {
  if (props.threshold == null) return null;
  return Math.max(0, Math.min(100, props.threshold * 100));
});
</script>

<template>
  <div class="or-meter" :class="[`or-meter--${size}`, `or-meter--${tone}`]">
    <div class="or-meter__track" role="img" :aria-label="`Score ${pct(value)}`">
      <div class="or-meter__fill" :style="{ width: `${width}%` }" />
      <div v-if="tick != null" class="or-meter__tick" :style="{ left: `${tick}%` }" />
    </div>
    <span v-if="showLabel" class="or-meter__label or-num">{{ pct(value) }}</span>
  </div>
</template>
