<script setup lang="ts">
import { NIcon } from "naive-ui";
import { typeIcon, typeLabel } from "@/utils/typeMeta";
import Chip from "@/components/kit/Chip.vue";

const props = defineProps<{
  type: string;
}>();
</script>

<template>
  <Chip>
    <NIcon :size="12" :component="typeIcon(props.type)" />
    {{ typeLabel(props.type) }}
  </Chip>
</template>
