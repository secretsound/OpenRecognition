<script setup lang="ts">
defineProps<{
  title: string;
  description?: string;
}>();
</script>

<template>
  <header class="detail-header">
    <div class="detail-header__text">
      <h1 class="detail-header__title">{{ title }}</h1>
      <p v-if="description" class="detail-header__desc">{{ description }}</p>
      <div v-if="$slots.meta" class="detail-header__meta">
        <slot name="meta" />
      </div>
    </div>
    <div v-if="$slots.action" class="detail-header__action">
      <slot name="action" />
    </div>
  </header>
</template>

<style scoped>
.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.detail-header__title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.detail-header__desc {
  margin: 6px 0 0;
  max-width: 40rem;
  color: var(--n-text-color-3);
  font-size: 0.9rem;
  line-height: 1.45;
}

.detail-header__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.detail-header__action {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
</style>
