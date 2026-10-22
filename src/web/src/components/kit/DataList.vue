<script setup lang="ts" generic="T">
defineProps<{
  items: T[];
  getKey: (item: T) => string;
}>();
</script>

<template>
  <div class="or-datalist">
    <div class="or-datalist__table">
      <slot name="table" />
    </div>
    <div class="or-datalist__cards">
      <slot v-for="item in items" :key="getKey(item)" name="card" :item="item" />
    </div>
  </div>
</template>
