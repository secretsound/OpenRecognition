<script setup lang="ts">
import { NThing } from "naive-ui";

defineProps<{
  title: string;
  description?: string;
  sticky?: boolean;
}>();
</script>

<template>
  <header class="app-page-header" :class="{ sticky }">
    <div class="page-header-row">
      <NThing :title="title" content-style="margin-top: 4px;">
        <template v-if="description" #description>
          <span class="page-desc">{{ description }}</span>
        </template>
      </NThing>
      <div v-if="$slots.action" class="page-header-action">
        <slot name="action" />
      </div>
    </div>
    <div v-if="$slots.extra" class="page-header-extra">
      <slot name="extra" />
    </div>
  </header>
</template>

<style scoped>
.app-page-header {
  margin-bottom: var(--or-page-gap);
}

.app-page-header.sticky {
  position: sticky;
  top: 0;
  z-index: 10;
  padding-bottom: 8px;
  margin-bottom: calc(var(--or-page-gap) - 8px);
  background: inherit;
}

.page-header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.page-header-row :deep(.n-thing-header__title) {
  font-size: 1.5rem;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.25;
}

.page-desc {
  color: var(--n-text-color-3);
  font-size: 0.9rem;
  line-height: 1.45;
}

.page-header-action {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.page-header-extra {
  margin-top: var(--or-section-gap);
}
</style>
