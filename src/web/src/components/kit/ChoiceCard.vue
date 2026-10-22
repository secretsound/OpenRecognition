<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    description?: string;
    selected?: boolean;
    disabled?: boolean;
  }>(),
  { selected: false, disabled: false },
);

const emit = defineEmits<{
  select: [];
}>();
</script>

<template>
  <button
    type="button"
    class="or-choice"
    :class="{ 'is-selected': selected }"
    :aria-pressed="selected"
    :disabled="disabled"
    @click="emit('select')"
  >
    <span v-if="$slots.icon" class="or-choice__icon">
      <slot name="icon" />
    </span>
    <span class="or-choice__title">{{ title }}</span>
    <span v-if="description" class="or-choice__desc">{{ description }}</span>
  </button>
</template>
