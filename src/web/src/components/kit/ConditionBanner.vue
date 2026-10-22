<script setup lang="ts">
import { NButton, NIcon } from "naive-ui";
import { CloseOutline } from "@vicons/ionicons5";
import { useRouter } from "vue-router";
import type { Condition } from "@/composables/useConditions";

defineProps<{
  items: Condition[];
}>();

const emit = defineEmits<{
  dismiss: [id: string];
}>();

const router = useRouter();
</script>

<template>
  <div v-if="items.length" class="or-banners">
    <div
      v-for="item in items"
      :key="item.id"
      class="or-banner"
      :class="`or-banner--${item.tone}`"
      role="status"
    >
      <div class="or-banner__copy">
        <strong>{{ item.title }}</strong>
        <span>{{ item.detail }}</span>
      </div>
      <div class="or-banner__actions">
        <NButton v-if="item.to" size="small" secondary @click="router.push(item.to)">
          Open
        </NButton>
        <NButton
          quaternary
          circle
          size="small"
          :aria-label="`Dismiss ${item.title}`"
          @click="emit('dismiss', item.id)"
        >
          <template #icon>
            <NIcon><CloseOutline /></NIcon>
          </template>
        </NButton>
      </div>
    </div>
  </div>
</template>
