<script setup lang="ts">
import { computed } from "vue";
import { NSteps, NStep } from "naive-ui";
import type { EnrollmentOut } from "@/types/api";

const props = defineProps<{
  enrollment: EnrollmentOut;
  tested?: boolean;
}>();

const emit = defineEmits<{
  samples: [];
  evaluate: [];
  test: [];
}>();

const hasSamples = computed(() => props.enrollment.sample_count > 0);
const hasQuality = computed(() => props.enrollment.quality != null);

/** Hide once the user has run a recognition test (setup complete). */
const setupComplete = computed(() => props.tested === true);

const currentStep = computed(() => {
  if (hasQuality.value) return 4;
  if (hasSamples.value) return 3;
  return 2;
});
</script>

<template>
  <div v-if="!setupComplete" class="setup-stepper" role="status" aria-label="Enrollment setup progress">
    <NSteps :current="currentStep" size="small">
      <NStep title="Created" />
      <NStep>
        <template #title>
          <button
            v-if="!hasSamples"
            type="button"
            class="step-link"
            @click="emit('samples')"
          >
            Samples
          </button>
          <span v-else>Samples</span>
        </template>
      </NStep>
      <NStep>
        <template #title>
          <button
            v-if="hasSamples && !hasQuality"
            type="button"
            class="step-link"
            @click="emit('evaluate')"
          >
            Quality
          </button>
          <span v-else>Quality</span>
        </template>
      </NStep>
      <NStep>
        <template #title>
          <button
            v-if="hasQuality && !tested"
            type="button"
            class="step-link"
            @click="emit('test')"
          >
            Try a match
          </button>
          <span v-else>Try a match</span>
        </template>
      </NStep>
    </NSteps>
  </div>
</template>

<style scoped>
.setup-stepper {
  padding: 14px 16px;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  background: var(--n-action-color);
}

.setup-stepper :deep(.n-step-content-header__title) {
  font-size: 0.8125rem;
}

.step-link {
  padding: 0;
  border: none;
  background: none;
  color: var(--n-primary-color);
  font: inherit;
  cursor: pointer;
  text-decoration: underline;
}
</style>
