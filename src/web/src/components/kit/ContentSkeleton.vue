<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: "table" | "list" | "form" | "detail" | "cards";
    rows?: number;
  }>(),
  { variant: "list", rows: 5 },
);
</script>

<template>
  <div class="or-skel" :class="`or-skel--${variant}`" aria-busy="true" aria-label="Loading">
    <template v-if="variant === 'detail'">
      <div class="or-skel__line or-skel__line--title" />
      <div class="or-skel__line or-skel__line--desc" />
      <div class="or-skel__row">
        <div class="or-skel__block" />
        <div class="or-skel__block" />
        <div class="or-skel__block" />
      </div>
    </template>
    <template v-else-if="variant === 'cards'">
      <div v-for="i in 3" :key="i" class="or-skel__card" />
    </template>
    <template v-else-if="variant === 'form'">
      <div v-for="i in rows" :key="i" class="or-skel__form-row">
        <div class="or-skel__line or-skel__line--label" />
        <div class="or-skel__line" />
      </div>
    </template>
    <template v-else>
      <div v-for="i in rows" :key="i" class="or-skel__line" :style="{ width: `${70 + ((i * 13) % 25)}%` }" />
    </template>
  </div>
</template>
