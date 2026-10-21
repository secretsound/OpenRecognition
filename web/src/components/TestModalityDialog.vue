<script setup lang="ts">
import { NButton, NModal } from "naive-ui";
import type { TestModality } from "@/utils/testModality";

defineProps<{
  show: boolean;
  label: string;
}>();

const emit = defineEmits<{
  "update:show": [value: boolean];
  pick: [modality: TestModality];
}>();
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    title="Voice or photo?"
    class="or-modal or-modal--narrow"
    @update:show="emit('update:show', $event)"
  >
    <p class="chooser-copy">
      {{ label }} has both a voice and a face. Pick which one to check.
    </p>
    <template #footer>
      <div class="or-modal-footer">
        <NButton @click="emit('update:show', false)">Cancel</NButton>
        <NButton @click="emit('pick', 'image')">Photo</NButton>
        <NButton type="primary" @click="emit('pick', 'audio')">Voice</NButton>
      </div>
    </template>
  </NModal>
</template>

<style scoped>
.chooser-copy {
  margin: 0 0 16px;
  line-height: 1.5;
}
</style>
