<script setup lang="ts">
import { computed } from "vue";
import { NTag } from "naive-ui";
import type { EnrollmentType } from "@/types/api";

const props = defineProps<{
  type: EnrollmentType | string;
}>();

const config = computed(() => {
  const map: Record<string, { label: string; class: string }> = {
    person: { label: "Person", class: "modality-person" },
    pet: { label: "Pet", class: "modality-pet" },
    object: { label: "Object", class: "modality-object" },
    sound: { label: "Sound", class: "modality-sound" },
  };
  return map[props.type] ?? { label: props.type, class: "" };
});
</script>

<template>
  <NTag
    size="small"
    round
    :bordered="false"
    class="type-tag"
    :class="config.class"
  >
    {{ config.label }}
  </NTag>
</template>

<style scoped>
.type-tag.modality-person {
  color: var(--or-modality-image);
  background: color-mix(in srgb, var(--or-modality-image) 18%, transparent);
}

.type-tag.modality-pet {
  color: var(--or-modality-pet);
  background: color-mix(in srgb, var(--or-modality-pet) 18%, transparent);
}

.type-tag.modality-object {
  color: var(--or-modality-object);
  background: color-mix(in srgb, var(--or-modality-object) 22%, transparent);
}

.type-tag.modality-sound {
  color: var(--or-modality-audio);
  background: color-mix(in srgb, var(--or-modality-audio) 18%, transparent);
}
</style>
