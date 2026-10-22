<script setup lang="ts">
import { computed } from "vue";
import {
  NModal,
  NDescriptions,
  NDescriptionsItem,
  NTag,
  NSpace,
  NButton,
  NPopconfirm,
  NDivider,
} from "naive-ui";
import type { SampleOut } from "@/types/api";
import {
  formatFitPct,
  formatSampleDuration,
  formatSampleSize,
  sampleFlagLabels,
  sampleSourceLabels,
} from "@/utils/sampleLabels";
import { formatAbsolute } from "@/utils/time";

const show = defineModel<boolean>("show", { required: true });

const props = withDefaults(
  defineProps<{
    sample: SampleOut | null;
    deleting?: boolean;
    canDelete?: boolean;
  }>(),
  { canDelete: true },
);

const emit = defineEmits<{
  delete: [];
}>();

const title = computed(() => props.sample?.source_label ?? "Sample details");

function modalityLabel(mod: string): string {
  if (mod === "audio") return "Voice";
  if (mod === "image") return "Face";
  return mod;
}
</script>

<template>
  <NModal
    v-model:show="show"
    preset="card"
    :title="title"
    class="sample-detail-modal or-modal or-modal--narrow"
    :mask-closable="true"
  >
    <template v-if="sample">
      <NSpace align="center" :size="8" class="sample-detail-tags">
        <NTag size="small" :bordered="false" type="info">
          {{ sampleSourceLabels[sample.source] ?? sample.source }}
        </NTag>
        <NTag size="small" :bordered="false">{{ modalityLabel(sample.modality) }}</NTag>
        <NTag
          v-if="sample.centroid_similarity != null"
          size="small"
          :bordered="false"
          :type="sample.centroid_similarity < 0.5 ? 'warning' : 'success'"
        >
          Fit {{ formatFitPct(sample.centroid_similarity) }}
        </NTag>
      </NSpace>

      <section v-if="sample.phrase_text" class="phrase-block">
        <h3 class="section-label">Phrase</h3>
        <p v-if="sample.phrase_index != null" class="phrase-index">
          Phrase {{ sample.phrase_index + 1 }}
        </p>
        <p class="phrase-text">{{ sample.phrase_text }}</p>
      </section>

      <NDivider v-if="sample.phrase_text" style="margin: 14px 0" />

      <NDescriptions :column="1" label-placement="left" size="small" class="sample-desc">
        <NDescriptionsItem label="Source label">
          {{ sample.source_label }}
        </NDescriptionsItem>
        <NDescriptionsItem v-if="sample.original_filename" label="Filename">
          <code class="mono">{{ sample.original_filename }}</code>
        </NDescriptionsItem>
        <NDescriptionsItem v-if="sample.content_type" label="Content type">
          {{ sample.content_type }}
        </NDescriptionsItem>
        <NDescriptionsItem label="Duration">
          {{
            sample.modality === "audio"
              ? formatSampleDuration(sample.duration_ms)
              : "—"
          }}
        </NDescriptionsItem>
        <NDescriptionsItem label="Size">
          {{ formatSampleSize(sample.size_bytes) }}
        </NDescriptionsItem>
        <NDescriptionsItem label="Model">
          <NTag
            size="tiny"
            :bordered="false"
            :type="sample.flags.includes('outdated_model') ? 'warning' : 'default'"
          >
            {{ sample.model_version }}
          </NTag>
        </NDescriptionsItem>
        <NDescriptionsItem label="File kept">
          {{
            sample.media_stored
              ? "Yes"
              : "No. Only the voice or face pattern is stored."
          }}
        </NDescriptionsItem>
        <NDescriptionsItem label="Flags">
          <NSpace v-if="sample.flags.length" size="small">
            <NTag
              v-for="f in sample.flags"
              :key="f"
              size="tiny"
              round
              :bordered="false"
              :type="sampleFlagLabels[f]?.type ?? 'default'"
            >
              {{ sampleFlagLabels[f]?.label ?? f }}
            </NTag>
          </NSpace>
          <span v-else class="muted">None</span>
        </NDescriptionsItem>
        <NDescriptionsItem label="Added">
          {{ formatAbsolute(sample.created_at) }}
        </NDescriptionsItem>
        <NDescriptionsItem label="Sample ID">
          <code class="mono">{{ sample.id }}</code>
        </NDescriptionsItem>
      </NDescriptions>
    </template>

    <template #footer>
      <NSpace justify="end">
        <NButton @click="show = false">Close</NButton>
        <NPopconfirm v-if="sample && canDelete" @positive-click="emit('delete')">
          <template #trigger>
            <NButton type="error" :loading="deleting">Delete sample</NButton>
          </template>
          Remove this sample permanently?
        </NPopconfirm>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
.sample-detail-tags {
  margin-bottom: 12px;
}

.section-label {
  margin: 0 0 6px;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--n-text-color-2);
}

.phrase-block {
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid var(--n-border-color);
  background: var(--n-action-color);
}

.phrase-index {
  margin: 0 0 6px;
  font-size: 0.75rem;
  color: var(--n-text-color-3);
}

.phrase-text {
  margin: 0;
  font-size: 0.9375rem;
  line-height: 1.5;
  color: var(--n-text-color-1);
  white-space: pre-wrap;
  word-break: break-word;
}

.sample-desc :deep(.n-descriptions-table-content) {
  word-break: break-word;
}

.mono {
  font-size: 0.75rem;
  word-break: break-all;
}

.muted {
  color: var(--n-text-color-3);
}
</style>
