<script setup lang="ts">
defineProps<{
  active?: boolean;
}>();

const emit = defineEmits<{
  clear: [];
}>();
</script>

<template>
  <div class="or-filters">
    <slot />
    <button v-if="active" type="button" class="or-filters__clear" @click="emit('clear')">
      Clear
    </button>
  </div>
</template>
