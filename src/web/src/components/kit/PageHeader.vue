<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    description?: string;
    width?: "page" | "prose";
  }>(),
  { width: "page" },
);
</script>

<template>
  <header class="or-page-header" :class="{ 'or-page-header--prose': width === 'prose' }">
    <div class="or-page-header__row">
      <div class="or-page-header__identity">
        <div v-if="$slots.lead" class="or-page-header__lead">
          <slot name="lead" />
        </div>
        <div class="or-page-header__copy">
          <h1 class="or-title">{{ title }}</h1>
          <p v-if="description" class="or-page-header__desc">{{ description }}</p>
          <div v-if="$slots.meta" class="or-page-header__meta">
            <slot name="meta" />
          </div>
        </div>
      </div>
      <div v-if="$slots.action" class="or-page-header__action">
        <slot name="action" />
      </div>
    </div>
    <div v-if="$slots.extra" class="or-page-header__extra">
      <slot name="extra" />
    </div>
    <div v-if="$slots.tabs" class="or-page-header__tabs">
      <slot name="tabs" />
    </div>
  </header>
</template>
