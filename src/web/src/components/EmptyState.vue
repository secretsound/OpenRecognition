<script setup lang="ts">
import type { Component } from "vue";
import { NButton, NIcon } from "naive-ui";

defineProps<{
  title: string;
  description?: string;
  icon?: Component;
  actionLabel?: string;
}>();

const emit = defineEmits<{
  action: [];
}>();
</script>

<template>
  <div class="or-empty">
    <div v-if="icon" class="or-empty__icon">
      <NIcon :size="36" :component="icon" />
    </div>
    <h2 class="or-heading">{{ title }}</h2>
    <p v-if="description" class="or-empty__desc">{{ description }}</p>
    <NButton v-if="actionLabel" type="primary" @click="emit('action')">
      {{ actionLabel }}
    </NButton>
  </div>
</template>

<style scoped>
.or-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--or-space-3);
  padding: var(--or-space-12) var(--or-space-6);
}

.or-empty__icon {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  border-radius: var(--or-radius-lg);
  background: var(--or-surface-sunken);
  color: var(--or-text-3);
}

.or-empty__desc {
  max-width: 28rem;
  color: var(--or-text-3);
  font-size: var(--or-text-body);
  line-height: var(--or-leading);
}
</style>
