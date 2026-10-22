<script setup lang="ts">
import { computed } from "vue";
import { formatAbsolute, formatRelative } from "@/utils/time";

const props = defineProps<{
  value: string | number | Date | null | undefined;
}>();

const relative = computed(() => (props.value ? formatRelative(props.value) : "—"));
const absolute = computed(() => (props.value ? formatAbsolute(props.value) : ""));
</script>

<template>
  <time class="or-time" :datetime="value ? String(value) : undefined" :title="absolute">
    {{ relative }}
  </time>
</template>
