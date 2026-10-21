<script setup lang="ts">
import type { Component } from "vue";
import { NButton, NEmpty } from "naive-ui";

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
  <div class="empty-wrap">
    <NEmpty :description="title" size="large">
      <template v-if="icon" #icon>
        <component :is="icon" class="empty-icon" />
      </template>
      <template #extra>
        <p v-if="description" class="empty-desc">{{ description }}</p>
        <NButton v-if="actionLabel" type="primary" @click="emit('action')">
          {{ actionLabel }}
        </NButton>
      </template>
    </NEmpty>
  </div>
</template>

<style scoped>
.empty-wrap {
  padding: 48px 24px;
}

.empty-icon {
  width: 48px;
  height: 48px;
  opacity: 0.45;
}

.empty-desc {
  margin: 0 0 16px;
  color: var(--n-text-color-3);
  font-size: 0.9rem;
}
</style>
