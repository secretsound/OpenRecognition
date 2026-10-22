<script setup lang="ts">
import { NModal, NSteps, NStep } from "naive-ui";

export interface WizardStepMeta {
  title: string;
  description?: string;
}

withDefaults(
  defineProps<{
    show: boolean;
    title: string;
    steps: WizardStepMeta[];
    current: number;
    maskClosable?: boolean;
    layout?: "steps" | "progress";
  }>(),
  { layout: "steps" },
);

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
    <div class="wizard-layout" :class="{ 'wizard-layout--progress': layout === 'progress' }">
      <p class="wizard-progress">
        Step {{ current + 1 }} of {{ steps.length }}
        <span v-if="steps[current]"> — {{ steps[current].title }}</span>
      </p>
      <NSteps
        v-if="layout === 'steps'"
        :current="current + 1"
        vertical
        size="small"
        class="wizard-steps"
      >
        <NStep
          v-for="(s, i) in steps"
          :key="i"
          :title="s.title"
          :description="s.description"
        />
      </NSteps>
      <div v-else class="wizard-meter">
        <div class="wizard-meter__row">
          <span>{{ steps[current]?.title ?? "Step" }}</span>
          <span>{{ current + 1 }} / {{ steps.length }}</span>
        </div>
        <div class="wizard-meter__track" aria-hidden="true">
          <i :style="{ width: `${((current + 1) / Math.max(1, steps.length)) * 100}%` }" />
        </div>
        <div v-if="steps.length > 3" class="wizard-meter__dots">
          <span
            v-for="(_, i) in steps"
            :key="i"
            :class="{
              'is-done': i < current,
              'is-current': i === current,
            }"
          />
        </div>
      </div>
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

.wizard-layout--progress {
  flex-direction: column;
  gap: 16px;
}

.wizard-meter {
  width: 100%;
}

.wizard-meter__row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--or-text-2);
}

.wizard-meter__track {
  margin-top: 8px;
  height: 6px;
  border-radius: 999px;
  background: var(--or-surface-sunken);
  overflow: hidden;
}

.wizard-meter__track i {
  display: block;
  height: 100%;
  background: var(--or-accent);
}

.wizard-meter__dots {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 10px;
}

.wizard-meter__dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--or-line);
}

.wizard-meter__dots .is-done {
  background: var(--or-accent);
}

.wizard-meter__dots .is-current {
  background: var(--or-text-1);
  outline: 2px solid color-mix(in oklab, var(--or-accent) 50%, transparent);
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
