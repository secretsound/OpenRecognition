<script setup lang="ts">
defineProps<{
  label: string;
  hint?: string;
}>();
</script>

<template>
  <div class="setting-row">
    <div class="setting-row__main">
      <span class="setting-row__label">{{ label }}</span>
      <div class="setting-row__control">
        <slot />
      </div>
    </div>
    <p v-if="hint || $slots.hint" class="setting-row__hint">
      <slot name="hint">{{ hint }}</slot>
    </p>
  </div>
</template>

<style scoped>
.setting-row {
  padding: 14px 0;
  border-bottom: 1px solid var(--n-border-color);
}

.setting-row:first-child {
  padding-top: 0;
}

.setting-row:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.setting-row__main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.setting-row__label {
  flex: 1;
  min-width: 0;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--n-text-color-1);
}

.setting-row__control {
  flex-shrink: 0;
}

.setting-row__hint {
  margin: 8px 0 0;
  max-width: 520px;
  font-size: 0.8rem;
  line-height: 1.45;
  color: var(--n-text-color-3);
}

.setting-row__hint :deep(code) {
  font-size: 0.75rem;
}

@media (max-width: 640px) {
  .setting-row__main {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .setting-row__control {
    width: 100%;
  }
}
</style>
