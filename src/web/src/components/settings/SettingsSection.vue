<script setup lang="ts">
defineProps<{
  title: string;
  description?: string;
}>();
</script>

<template>
  <section class="settings-section">
    <header v-if="title" class="settings-section__head">
      <h3 class="settings-section__title">{{ title }}</h3>
      <p v-if="description" class="settings-section__desc">{{ description }}</p>
    </header>
    <div class="settings-section__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.settings-section {
  padding: 16px 18px;
  border-radius: 10px;
  border: 1px solid var(--n-border-color);
  background: var(--n-color-modal);
}

.settings-section + .settings-section {
  margin-top: 12px;
}

.settings-section__head {
  margin-bottom: 14px;
}

.settings-section__title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.settings-section__desc {
  margin: 6px 0 0;
  font-size: 0.8125rem;
  line-height: 1.45;
  color: var(--n-text-color-3);
}

.settings-section__body :deep(.n-form-item:last-child) {
  margin-bottom: 0;
}
</style>
