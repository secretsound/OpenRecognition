<script setup lang="ts">
import { computed } from "vue";
import type { EnrollmentOut } from "@/types/api";
import { enrollmentStatus } from "@/utils/enrollmentStatus";
import Chip from "@/components/kit/Chip.vue";

const props = defineProps<{
  enrollment: Pick<EnrollmentOut, "enabled" | "sample_count" | "quality">;
}>();

const status = computed(() => enrollmentStatus(props.enrollment));
</script>

<template>
  <Chip :tone="status.tone">{{ status.label }}</Chip>
</template>
