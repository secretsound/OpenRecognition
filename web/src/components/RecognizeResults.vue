<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import {
  NCard,
  NTag,
  NProgress,
  NDataTable,
  NButton,
  NAlert,
  NSpace,
  NDescriptions,
  NDescriptionsItem,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import { h } from "vue";
import type { CandidateMatch, EntityResult, RecognizeResponse } from "@/types/api";
import TypeTag from "@/components/TypeTag.vue";

const props = defineProps<{
  result: RecognizeResponse;
  expectedLabel?: string | null;
  minConfidence?: number;
}>();

const router = useRouter();

const bestMatch = computed(() => {
  const known = props.result.entities.filter((e) => e.label !== "unknown");
  if (known.length === 0) return null;
  return [...known].sort((a, b) => b.confidence - a.confidence)[0];
});

const unknownEntity = computed(() =>
  props.result.entities.find((e) => e.label === "unknown") ?? null,
);

const isUnknown = computed(() => {
  if (props.result.entities.length === 0) return true;
  return props.result.entities.every((e) => e.label === "unknown");
});

const topCandidate = computed(() => {
  const cands = props.result.diagnostics?.candidates ?? [];
  if (cands.length === 0) return null;
  return [...cands].sort((a, b) => b.confidence - a.confidence)[0];
});

const expectationMet = computed(() => {
  if (!props.expectedLabel || !bestMatch.value) return null;
  return bestMatch.value.label.toLowerCase() === props.expectedLabel.toLowerCase();
});

function confidenceStatus(conf: number, accepted?: boolean) {
  if (accepted === false) return "default";
  const pct = Math.round(conf * 100);
  if (pct >= 75) return "success";
  if (pct >= 50) return "warning";
  return "default";
}

function renderConfidence(conf: number, accepted?: boolean) {
  const pct = Math.round(conf * 100);
  return h(NProgress, {
    type: "line",
    percentage: pct,
    indicatorPlacement: "inside",
    status: confidenceStatus(conf, accepted),
  });
}

const entityColumns: DataTableColumns<EntityResult> = [
  {
    title: "Label",
    key: "label",
    render(row) {
      return h("span", { style: { fontWeight: row.label !== "unknown" ? 600 : 400 } }, row.label);
    },
  },
  {
    title: "Type",
    key: "type",
    width: 100,
    render(row) {
      return h(TypeTag, { type: row.type });
    },
  },
  {
    title: "Confidence",
    key: "confidence",
    width: 140,
    render(row) {
      return renderConfidence(row.confidence);
    },
  },
  {
    title: "Threshold",
    key: "threshold_used",
    width: 90,
    render(row) {
      if (row.threshold_used == null) return "—";
      return `${Math.round(row.threshold_used * 100)}%`;
    },
  },
  {
    title: "Pipeline",
    key: "recognition_type",
    width: 110,
  },
  {
    title: "",
    key: "link",
    width: 80,
    render(row) {
      if (!row.entity_id) return "—";
      return h(
        NButton,
        {
          text: true,
          type: "primary",
          size: "small",
          onClick: () => router.push(`/enrollments/${row.entity_id}`),
        },
        { default: () => "View" },
      );
    },
  },
];

const candidateColumns: DataTableColumns<CandidateMatch> = [
  {
    title: "Label",
    key: "label",
    render(row) {
      return h("span", { style: { fontWeight: 600 } }, row.label);
    },
  },
  {
    title: "Type",
    key: "type",
    width: 90,
    render(row) {
      return h(TypeTag, { type: row.type });
    },
  },
  {
    title: "Similarity",
    key: "confidence",
    width: 140,
    render(row) {
      return renderConfidence(row.confidence, row.accepted);
    },
  },
  {
    title: "Needs",
    key: "threshold_used",
    width: 80,
    render(row) {
      const t = row.threshold_used ?? props.minConfidence ?? 0.75;
      const base = `${Math.round(t * 100)}%`;
      if (row.enrollment_threshold != null && row.enrollment_threshold !== t) {
        return `${base} (enr. ${Math.round(row.enrollment_threshold * 100)}%)`;
      }
      return base;
    },
  },
  {
    title: "Status",
    key: "accepted",
    width: 110,
    render(row) {
      return h(
        NTag,
        { size: "small", type: row.accepted ? "success" : "default", bordered: false },
        { default: () => (row.accepted ? "Would match" : "Below threshold") },
      );
    },
  },
  {
    title: "Pipeline",
    key: "recognition_type",
    width: 100,
  },
  {
    title: "",
    key: "link",
    width: 80,
    render(row) {
      return h(
        NButton,
        {
          text: true,
          type: "primary",
          size: "small",
          onClick: () => router.push(`/enrollments/${row.entity_id}`),
        },
        { default: () => "View" },
      );
    },
  },
];
</script>

<template>
  <div class="results">
    <NAlert
      v-if="expectedLabel && expectationMet === true"
      type="success"
      title="Expected match"
      style="margin-bottom: 16px"
    >
      Recognized as <strong>{{ bestMatch?.label }}</strong> (expected {{ expectedLabel }}).
    </NAlert>
    <NAlert
      v-else-if="expectedLabel && expectationMet === false && bestMatch"
      type="warning"
      title="Different match"
      style="margin-bottom: 16px"
    >
      Expected <strong>{{ expectedLabel }}</strong>, but best match is
      <strong>{{ bestMatch.label }}</strong> ({{ Math.round(bestMatch.confidence * 100) }}%).
    </NAlert>
    <NAlert
      v-else-if="expectedLabel && isUnknown && !bestMatch"
      type="error"
      title="No match"
      style="margin-bottom: 16px"
    >
      Expected <strong>{{ expectedLabel }}</strong>, but no enrolled identity matched.
    </NAlert>

    <NCard
      v-if="bestMatch && !isUnknown"
      class="hero-match"
      :bordered="false"
      size="small"
    >
      <div class="hero-inner">
        <div>
          <p class="hero-kicker">This matches</p>
          <h3 class="hero-label">{{ bestMatch.label }}</h3>
          <NSpace :size="8" style="margin-top: 8px">
            <TypeTag :type="bestMatch.type" />
            <NTag size="small" :bordered="false">{{ bestMatch.recognition_type }}</NTag>
          </NSpace>
        </div>
        <div class="hero-score">
          <span class="score-value">{{ Math.round(bestMatch.confidence * 100) }}%</span>
          <span class="score-caption">similarity</span>
        </div>
      </div>
      <NButton
        v-if="bestMatch.entity_id"
        text
        type="primary"
        style="margin-top: 12px"
        @click="router.push(`/enrollments/${bestMatch.entity_id}`)"
      >
        Open enrollment →
      </NButton>
    </NCard>

    <NAlert
      v-else-if="unknownEntity"
      type="info"
      title="Below threshold — closest gallery hit"
      style="margin-bottom: 16px"
    >
      Best similarity was <strong>{{ Math.round(unknownEntity.confidence * 100) }}%</strong>
      (returned as <em>unknown</em>). Lower min confidence or check enrollment quality.
    </NAlert>

    <NAlert
      v-else-if="isUnknown && topCandidate"
      type="info"
      title="No accepted match"
      style="margin-bottom: 16px"
    >
      Closest enrolled identity:
      <strong>{{ topCandidate.label }}</strong> at
      <strong>{{ Math.round(topCandidate.confidence * 100) }}%</strong>
      (needs {{ Math.round((topCandidate.threshold_used ?? minConfidence ?? 0.75) * 100) }}% on this test).
    </NAlert>

    <NAlert
      v-else-if="isUnknown && !topCandidate"
      type="warning"
      title="No gallery similarity"
      style="margin-bottom: 16px"
    >
      Nothing in the gallery was close enough to report
      <span v-if="result.diagnostics?.pipelines.length">
        (pipelines: {{ result.diagnostics.pipelines.join(", ") }}).
      </span>
      <span v-else> — enroll matching modalities or try different media.</span>
    </NAlert>

    <NCard
      v-if="result.diagnostics"
      title="Troubleshooting"
      :bordered="false"
      size="small"
      style="margin-bottom: 16px"
    >
      <NDescriptions v-if="result.diagnostics.pipelines.length" :column="1" size="small" label-placement="left">
        <NDescriptionsItem label="Pipelines run">
          {{ result.diagnostics.pipelines.join(", ") }}
        </NDescriptionsItem>
        <NDescriptionsItem v-if="minConfidence != null" label="Min confidence (request)">
          {{ Math.round(minConfidence * 100) }}%
        </NDescriptionsItem>
      </NDescriptions>
      <ul v-if="result.diagnostics.notes.length" class="diag-notes">
        <li v-for="(note, i) in result.diagnostics.notes" :key="i">{{ note }}</li>
      </ul>
      <NDataTable
        v-if="result.diagnostics.candidates.length"
        :columns="candidateColumns"
        :data="result.diagnostics.candidates"
        :bordered="false"
        size="small"
        style="margin-top: 12px"
      />
      <p v-else class="diag-empty">No ranked candidates — gallery may be empty or embedding sizes differ.</p>
    </NCard>

    <NCard
      v-if="result.gate"
      title="Audio gate"
      :bordered="false"
      size="small"
      style="margin-bottom: 16px"
    >
      <NSpace align="center" :size="12">
        <NTag :type="result.gate === 'accept' ? 'success' : 'warning'" size="medium">
          {{ result.gate }}
        </NTag>
        <span v-if="result.reason" class="gate-reason">{{ result.reason }}</span>
      </NSpace>
      <div v-if="result.scores && Object.keys(result.scores).length" class="gate-scores">
        <div v-for="(val, key) in result.scores" :key="key" class="score-row">
          <span>{{ key }}</span>
          <span>{{ Math.round(val * 100) }}%</span>
        </div>
      </div>
      <p v-if="result.gate === 'reject'" class="gate-hint">
        Speaker identification was skipped because the gate rejected this audio.
      </p>
    </NCard>

    <NCard v-if="result.entities.length" title="API entities" :bordered="false" size="small">
      <p class="section-hint">What the recognition endpoint returned (matches and unknowns).</p>
      <NDataTable
        :columns="entityColumns"
        :data="result.entities"
        :bordered="false"
        size="small"
      />
    </NCard>

    <p class="meta-line">
      {{ result.meta.latency_ms.toFixed(0) }} ms
      <span v-if="result.meta.dry_run"> · sandbox (no webhooks)</span>
      <span v-if="result.meta.request_id"> · {{ result.meta.request_id }}</span>
    </p>
  </div>
</template>

<style scoped>
.hero-match {
  margin-bottom: 16px;
  background: linear-gradient(
    135deg,
    rgba(24, 160, 88, 0.12) 0%,
    rgba(24, 160, 88, 0.04) 100%
  );
}

.hero-inner {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.hero-kicker {
  margin: 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--n-text-color-3);
}

.hero-label {
  margin: 4px 0 0;
  font-size: 1.5rem;
  font-weight: 600;
}

.hero-score {
  text-align: right;
}

.score-value {
  display: block;
  font-size: 2rem;
  font-weight: 700;
  color: var(--n-primary-color);
  line-height: 1;
}

.score-caption {
  font-size: 0.75rem;
  color: var(--n-text-color-3);
}

.gate-reason {
  color: var(--n-text-color-2);
  font-size: 0.875rem;
}

.gate-scores {
  margin-top: 12px;
  display: grid;
  gap: 6px;
}

.score-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: var(--n-text-color-2);
}

.gate-hint,
.section-hint,
.diag-empty {
  margin: 12px 0 0;
  font-size: 0.8rem;
  color: var(--n-text-color-3);
}

.diag-notes {
  margin: 8px 0 0;
  padding-left: 1.2rem;
  font-size: 0.85rem;
  color: var(--n-text-color-2);
}

.meta-line {
  margin: 16px 0 0;
  font-size: 0.75rem;
  color: var(--n-text-color-3);
}
</style>
