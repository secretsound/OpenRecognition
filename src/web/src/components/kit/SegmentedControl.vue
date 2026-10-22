<script setup lang="ts" generic="T extends string">
defineProps<{
  options: { value: T; label: string; hint?: string }[];
  ariaLabel?: string;
}>();

const model = defineModel<T>({ required: true });
</script>

<template>
  <div class="or-segment" role="tablist" :aria-label="ariaLabel">
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      role="tab"
      class="or-segment__item"
      :class="{ 'is-active': model === opt.value }"
      :aria-selected="model === opt.value"
      :title="opt.hint"
      @click="model = opt.value"
    >
      {{ opt.label }}
    </button>
  </div>
</template>
