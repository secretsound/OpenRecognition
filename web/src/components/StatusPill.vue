<script setup lang="ts">
import { computed } from "vue";
import { NTag } from "naive-ui";
import type { EnrollmentOut } from "@/types/api";
import { enrollmentStatus } from "@/utils/enrollmentStatus";

const props = defineProps<{
  enrollment: Pick<EnrollmentOut, "enabled" | "sample_count" | "quality">;
}>();

const status = computed(() => enrollmentStatus(props.enrollment));
</script>

<template>
  <NTag size="small" round :bordered="false" :type="status.type">
    {{ status.label }}
  </NTag>
</template>
