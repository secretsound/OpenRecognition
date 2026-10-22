<script setup lang="ts">
withDefaults(
  defineProps<{
    dirty: boolean;
    saving?: boolean;
    canSave?: boolean;
  }>(),
  {
    saving: false,
    canSave: true,
  },
);

const emit = defineEmits<{
  save: [];
  discard: [];
}>();
</script>

<template>
  <div v-if="dirty" class="or-savebar-slot" aria-hidden="true" />
  <Teleport to="body">
    <Transition name="or-fade">
      <div v-if="dirty" class="or-savebar" role="status">
        <span class="or-savebar__copy">Unsaved changes</span>
        <div class="or-savebar__actions">
          <button type="button" class="or-savebar__ghost" :disabled="saving" @click="emit('discard')">
            Discard
          </button>
          <button
            type="button"
            class="or-savebar__primary"
            :disabled="saving || !canSave"
            @click="emit('save')"
          >
            {{ saving ? "Saving…" : "Save" }}
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
