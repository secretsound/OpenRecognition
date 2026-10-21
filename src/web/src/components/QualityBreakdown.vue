<script setup lang="ts">
import { computed } from "vue";
import { NProgress, NStatistic, NTag, NTooltip } from "naive-ui";
import type { ModalityQuality, QualityInfo } from "@/types/api";
import { issueLabel } from "@/utils/qualityLabels";

const props = defineProps<{
  quality: QualityInfo;
}>();

const overallPct = computed(() => Math.round(props.quality.score * 100));

const modalities = computed(() => props.quality.modalities ?? []);

const hasBreakdown = computed(() => modalities.value.length > 0);

function modalityPct(mod: ModalityQuality): number {
  return Math.round(mod.score * 100);
}

function progressStatus(
  mod: ModalityQuality,
): "success" | "warning" | "default" | "error" {
  if (mod.sample_count === 0) return "default";
  return mod.usable ? "success" : "warning";
}

function modalityColor(mod: ModalityQuality): string | undefined {
  if (mod.sample_count === 0) return undefined;
  if (mod.modality === "audio") return "var(--or-modality-audio)";
  if (mod.modality === "image") return "var(--or-modality-image)";
  return undefined;
}

function statusLabel(mod: ModalityQuality): string {
  if (mod.sample_count === 0) return "Missing";
  return mod.usable ? "Good" : "Needs work";
}

function statusTagType(mod: ModalityQuality): "success" | "warning" | "default" {
  if (mod.sample_count === 0) return "default";
  return mod.usable ? "success" : "warning";
}
</script>

<template>
  <div class="quality-breakdown">
    <div class="overall">
      <NStatistic label="Overall score" :value="overallPct">
        <template #suffix>%</template>
      </NStatistic>
      <NProgress
        type="line"
        :percentage="overallPct"
        :status="quality.usable ? 'success' : 'warning'"
        class="overall-bar"
      />
    </div>

    <div v-if="hasBreakdown" class="modality-grid">
      <div
        v-for="mod in modalities"
        :key="mod.modality"
        class="modality-tile"
        :class="`modality-tile--${mod.modality}`"
      >
        <NProgress
          type="circle"
          :percentage="modalityPct(mod)"
          :status="progressStatus(mod)"
          :color="modalityColor(mod)"
          :stroke-width="10"
          class="modality-ring"
        />
        <span class="modality-title">{{ mod.label }}</span>
        <div class="modality-meta">
          <span class="modality-samples">
            {{ mod.sample_count }} {{ mod.sample_count === 1 ? "sample" : "samples" }}
          </span>
          <NTag size="tiny" round :bordered="false" :type="statusTagType(mod)">
            {{ statusLabel(mod) }}
          </NTag>
        </div>
        <NTooltip v-if="mod.issues.length" trigger="hover" :style="{ maxWidth: '240px' }">
          <template #trigger>
            <p class="modality-issues modality-issues--warn">
              {{ mod.issues.length }} issue{{ mod.issues.length === 1 ? "" : "s" }}
            </p>
          </template>
          <ul class="issues-tooltip">
            <li v-for="issue in mod.issues" :key="issue">{{ issueLabel(issue) }}</li>
          </ul>
        </NTooltip>
        <p v-else-if="mod.sample_count > 0" class="modality-issues modality-issues--ok">
          No issues
        </p>
        <p v-else class="modality-issues modality-issues--muted">No samples</p>
      </div>
    </div>

    <ul v-if="quality.issues.length && !hasBreakdown" class="issues-list">
      <li v-for="issue in quality.issues" :key="issue">{{ issueLabel(issue) }}</li>
    </ul>
    <p v-else-if="!hasBreakdown && quality.issues.length === 0" class="fallback-ok">
      No issues reported.
    </p>
  </div>
</template>

<style scoped>
.quality-breakdown {
  width: 100%;
}

.overall {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--n-border-color);
}

.overall-bar {
  margin-top: 10px;
}

.modality-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(108px, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.modality-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 4px;
  padding: 10px 8px;
  border-radius: 8px;
  border: 1px solid var(--n-border-color);
  background: var(--n-action-color);
}

.modality-ring {
  width: 80px;
}

.modality-ring :deep(.n-progress-text) {
  font-size: 0.7rem;
  font-weight: 600;
}

.modality-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.modality-meta {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.modality-samples {
  font-size: 0.7rem;
  color: var(--n-text-color-3);
}

.modality-issues {
  margin: 2px 0 0;
  font-size: 0.65rem;
  line-height: 1.3;
}

.modality-issues--ok {
  color: var(--n-success-color);
}

.modality-issues--warn {
  color: var(--n-warning-color);
  cursor: help;
  text-decoration: underline dotted;
}

.modality-issues--muted {
  color: var(--n-text-color-3);
}

.issues-tooltip {
  margin: 0;
  padding-left: 1rem;
  font-size: 0.8125rem;
  line-height: 1.4;
}

.issues-list {
  margin: 12px 0 0;
  padding-left: 1.2rem;
  color: var(--n-text-color-2);
  font-size: 0.8rem;
  line-height: 1.45;
}

.fallback-ok {
  margin: 12px 0 0;
  color: var(--n-text-color-3);
  font-size: 0.8rem;
}
</style>
