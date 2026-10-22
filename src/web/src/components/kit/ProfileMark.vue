<script setup lang="ts">
import { computed } from "vue";
import { NIcon } from "naive-ui";
import { initials, typeIcon } from "@/utils/typeMeta";

const props = withDefaults(
  defineProps<{
    label: string;
    type?: string;
    size?: "sm" | "md" | "lg" | "xl";
    src?: string | null;
  }>(),
  { size: "md" },
);

const letters = computed(() => initials(props.label));
const Icon = computed(() => (props.type ? typeIcon(props.type) : null));
</script>

<template>
  <span class="or-mark" :class="`or-mark--${size}`" :title="label" aria-hidden="true">
    <img v-if="src" :src="src" alt="" class="or-mark__img" />
    <span v-else class="or-mark__letters">{{ letters }}</span>
    <span v-if="Icon" class="or-mark__type">
      <NIcon :size="size === 'sm' ? 8 : size === 'xl' ? 14 : 10" :component="Icon" />
    </span>
  </span>
</template>
