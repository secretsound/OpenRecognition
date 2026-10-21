<script setup lang="ts">
import { NModal, NSteps, NStep } from "naive-ui";

export interface WizardStepMeta {
  title: string;
  description?: string;
}

defineProps<{
  show: boolean;
  title: string;
  steps: WizardStepMeta[];
  current: number;
  maskClosable?: boolean;
}>();

const emit = defineEmits<{
  "update:show": [value: boolean];
}>();
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    class="guided-modal"
    :title="title"
    :mask-closable="maskClosable ?? false"
    @update:show="emit('update:show', $event)"
  >
    <div class="wizard-layout">
      <p class="wizard-progress">
        Step {{ current + 1 }} of {{ steps.length }}
        <span v-if="steps[current]"> — {{ steps[current].title }}</span>
      </p>
      <NSteps :current="current + 1" vertical size="small" class="wizard-steps">
        <NStep
          v-for="(s, i) in steps"
          :key="i"
          :title="s.title"
          :description="s.description"
        />
      </NSteps>
      <div class="wizard-content">
        <slot />
      </div>
    </div>
    <template v-if="$slots.footer" #footer>
      <slot name="footer" />
    </template>
  </NModal>
</template>

<style scoped>
.guided-modal :deep(.n-card__content) {
  padding-top: 8px;
}

.wizard-layout {
  display: flex;
  gap: 28px;
  align-items: flex-start;
  min-height: 280px;
}

.wizard-steps {
  flex: 0 0 168px;
  padding-top: 4px;
}

.wizard-content {
  flex: 1;
  min-width: 0;
}

.wizard-progress {
  display: none;
  margin: 0;
  font-size: 0.875rem;
  font-weight: 600;
}

@media (max-width: 640px) {
  .wizard-layout {
    flex-direction: column;
    gap: 20px;
    min-height: 0;
  }

  .wizard-steps {
    display: none;
  }

  .wizard-progress {
    display: block;
  }
}
</style>
