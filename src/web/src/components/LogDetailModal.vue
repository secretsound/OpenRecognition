<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import {
  NModal,
  NDescriptions,
  NDescriptionsItem,
  NTag,
  NSpace,
  NButton,
  NDivider,
} from "naive-ui";
import type {
  RecognitionLogOut,
  RecognitionLogSpeakerCandidate,
} from "@/types/api";
import { formatLogEvent, formatLogMedia } from "@/utils/logEvent";

const show = defineModel<boolean>("show", { required: true });

const props = defineProps<{
  log: RecognitionLogOut | null;
}>();

const router = useRouter();

const title = computed(() => {
  if (!props.log) return "Event details";
  const event = formatEvent(props.log.event);
  const label = props.log.label?.trim();
  if (!label || label.toLowerCase() === "unknown") return event;
  return `${event} — ${label}`;
});

const gateScores = computed(() => props.log?.details?.gate_scores ?? null);
const speakerCandidates = computed(
  () => props.log?.details?.speaker_candidates ?? [],
);
const timing = computed(() => props.log?.details?.timing_ms ?? null);
const minConfidence = computed(() => props.log?.details?.min_confidence ?? null);
const speakerMatchAttempted = computed(
  () => props.log?.details?.speaker_match_attempted === true,
);
const galleryCount = computed(() => props.log?.details?.gallery_count ?? null);
const comparableSpeakerCount = computed(
  () => props.log?.details?.comparable_speaker_count ?? null,
);
const speakerMatchSkipped = computed(
  () =>
    props.log?.modality === "audio" &&
    props.log?.gate === "reject" &&
    !speakerMatchAttempted.value &&
    speakerCandidates.value.length === 0,
);
const showSpeakerSection = computed(
  () => speakerMatchAttempted.value || speakerCandidates.value.length > 0,
);

function speakerMatchEmptyMessage(log: RecognitionLogOut) {
  const model = log.details?.speaker_model_version;
  if (log.reason === "empty_gallery" || galleryCount.value === 0) {
    return model
      ? `No enrollments with voice samples for model ${model}. Add audio samples to a person enrollment.`
      : "No enrollments with trained audio embeddings in the gallery.";
  }
  if (comparableSpeakerCount.value === 0) {
    return model
      ? `Enrollments exist but none have voice samples for model ${model}. Face-only enrollments won't match — add voice samples or re-enroll audio.`
      : "Enrollments exist but none are comparable for speaker ID (need person/sound enrollments with matching audio model dimensions).";
  }
  if (log.reason === "no_entities" || log.reason === "unknown_or_low_confidence") {
    return "Speaker ID ran but no enrollment met the confidence threshold.";
  }
  if (log.gate === "reject") {
    return "Speaker ID ran for logging; the gate rejected this clip before STT.";
  }
  return "No enrollment candidates ranked for this clip.";
}

function formatEvent(event: string) {
  return formatLogEvent(event);
}

function eventTagType(event: string) {
  if (event === "recognition.match") return "success";
  if (event === "recognition.unknown") return "warning";
  if (event.startsWith("enrollment.")) return "info";
  if (event === "recognition.gate_reject") return "error";
  if (event === "wyoming.transcript") return "success";
  if (event === "wyoming.blocked") return "warning";
  return "default";
}

function pct(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}% (${value.toFixed(3)})`;
}

function formatConfidence(log: RecognitionLogOut) {
  if (log.event.startsWith("enrollment.")) return "Not applicable";
  if (log.confidence != null) return pct(log.confidence);
  const top = log.details?.speaker_candidates?.[0];
  if (top) return `${top.label}: ${pct(top.confidence)}`;
  return "—";
}

function formatGateScore(label: string, value: number | undefined) {
  if (value == null) return null;
  return `${label}: ${pct(value)}`;
}

function candidateStatus(row: RecognitionLogSpeakerCandidate) {
  if (row.accepted) return "match";
  if (minConfidence.value != null && row.confidence >= minConfidence.value) return "above threshold";
  return "below threshold";
}

function formatActor(log: RecognitionLogOut) {
  if (!log.actor_name && !log.actor_type) return "—";
  const kind =
    log.actor_type === "api_key" ? "API key" : log.actor_type === "user" ? "User" : log.actor_type ?? "";
  if (log.actor_name && kind) return `${log.actor_name} (${kind})`;
  return log.actor_name ?? (kind || "—");
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  });
}

function openEnrollment() {
  if (!props.log?.entity_id) return;
  show.value = false;
  void router.push(`/enrollments/${props.log.entity_id}`);
}
</script>

<template>
  <NModal
    v-model:show="show"
    preset="card"
    :title="title"
    class="log-detail-modal or-modal"
    :mask-closable="true"
  >
    <template v-if="log">
      <NSpace align="center" :size="8" class="log-detail-tags">
        <NTag size="small" :bordered="false" :type="eventTagType(log.event)" round>
          {{ formatEvent(log.event) }}
        </NTag>
        <NTag v-if="log.modality" size="small" :bordered="false">{{ formatLogMedia(log.modality) }}</NTag>
        <NTag v-if="log.dry_run" size="small" :bordered="false" type="default">Practice</NTag>
        <NTag v-if="log.gate" size="small" :bordered="false" :type="log.gate === 'accept' ? 'success' : 'warning'">
          {{ log.gate === "accept" ? "Speech check passed" : "Speech check rejected" }}
        </NTag>
      </NSpace>

      <p v-if="log.summary || log.reason" class="log-summary">
        {{ log.summary ?? log.reason }}
      </p>
      <p class="log-raw">Event name: {{ log.event }}</p>

      <NDivider v-if="log.summary || log.reason" style="margin: 14px 0" />

      <section v-if="gateScores" class="log-section">
        <h4 class="log-section__title">Speech check</h4>
        <NSpace :size="8">
          <NTag v-if="gateScores.speech != null" size="small" :bordered="false" type="success">
            {{ formatGateScore("speech", gateScores.speech) }}
          </NTag>
          <NTag v-if="gateScores.music != null" size="small" :bordered="false" type="warning">
            {{ formatGateScore("music", gateScores.music) }}
          </NTag>
          <NTag v-if="gateScores.noise != null" size="small" :bordered="false" type="default">
            {{ formatGateScore("noise", gateScores.noise) }}
          </NTag>
        </NSpace>
      </section>

      <section v-if="speakerMatchSkipped" class="log-section">
        <h4 class="log-section__title">Speaker matching</h4>
        <p class="log-section__text">
          This clip did not sound like speech, so nobody was matched. The scores above describe
          the sound, not who was speaking.
        </p>
      </section>

      <section v-if="showSpeakerSection" class="log-section">
        <h4 class="log-section__title">
          Speaker candidates
          <span v-if="minConfidence != null" class="log-section__hint">
            (threshold {{ pct(minConfidence) }})
          </span>
        </h4>
        <ul v-if="speakerCandidates.length" class="candidate-list">
          <li v-for="(row, idx) in speakerCandidates" :key="`${row.label}-${idx}`" class="candidate-row">
            <span class="candidate-row__label">{{ row.label }}</span>
            <span class="candidate-row__score">{{ pct(row.confidence) }}</span>
            <NTag
              size="small"
              :bordered="false"
              :type="row.accepted ? 'success' : 'default'"
              round
            >
              {{ candidateStatus(row) }}
            </NTag>
          </li>
        </ul>
        <p v-else class="log-section__text">{{ speakerMatchEmptyMessage(log) }}</p>
      </section>

      <section v-if="timing" class="log-section">
        <h4 class="log-section__title">Timing</h4>
        <p class="log-section__text">
          identify {{ timing.identify ?? "—" }} ms · upstream {{ timing.upstream ?? "—" }} ms · total
          {{ timing.total ?? "—" }} ms
        </p>
      </section>

      <NDivider
        v-if="gateScores || speakerMatchSkipped || showSpeakerSection || timing"
        style="margin: 14px 0"
      />

      <NDescriptions :column="1" label-placement="left" size="small" class="log-desc">
        <NDescriptionsItem label="Time">{{ formatTime(log.created_at) }}</NDescriptionsItem>
        <NDescriptionsItem label="Event">{{ log.event }}</NDescriptionsItem>
        <NDescriptionsItem v-if="log.label" label="Label">{{ log.label }}</NDescriptionsItem>
        <NDescriptionsItem label="Confidence">{{ formatConfidence(log) }}</NDescriptionsItem>
        <NDescriptionsItem v-if="log.gate" label="Gate">{{ log.gate }}</NDescriptionsItem>
        <NDescriptionsItem v-if="log.reason" label="Reason">{{ log.reason }}</NDescriptionsItem>
        <NDescriptionsItem v-if="log.details?.transcript" label="Transcript">
          {{ log.details.transcript }}
        </NDescriptionsItem>
        <NDescriptionsItem v-if="log.details?.block_reason" label="Block reason">
          {{ log.details.block_reason }}
        </NDescriptionsItem>
        <NDescriptionsItem v-if="log.modality" label="Modality">{{ log.modality }}</NDescriptionsItem>
        <NDescriptionsItem v-if="log.camera_id" label="Camera">{{ log.camera_id }}</NDescriptionsItem>
        <NDescriptionsItem v-if="log.zone" label="Zone">{{ log.zone }}</NDescriptionsItem>
        <NDescriptionsItem label="Actor">{{ formatActor(log) }}</NDescriptionsItem>
        <NDescriptionsItem v-if="log.latency_ms != null" label="Latency">
          {{ Math.round(log.latency_ms) }} ms
        </NDescriptionsItem>
        <NDescriptionsItem label="Sandbox">{{ log.dry_run ? "Yes — webhooks skipped" : "No" }}</NDescriptionsItem>
        <NDescriptionsItem v-if="log.entity_id" label="Entity ID">
          <code class="mono">{{ log.entity_id }}</code>
        </NDescriptionsItem>
        <NDescriptionsItem v-if="log.request_id" label="Request ID">
          <code class="mono">{{ log.request_id }}</code>
        </NDescriptionsItem>
        <NDescriptionsItem label="Log ID">
          <code class="mono">{{ log.id }}</code>
        </NDescriptionsItem>
      </NDescriptions>

      <NSpace v-if="log.entity_id && log.event.startsWith('enrollment.')" :size="8" style="margin-top: 16px">
        <NButton type="primary" secondary @click="openEnrollment">Open enrollment</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
.log-detail-tags {
  margin-bottom: 4px;
}

.log-summary {
  margin: 10px 0 0;
  font-size: 0.9375rem;
  color: var(--n-text-color-2);
  line-height: 1.45;
}

.log-raw {
  margin: 6px 0 0;
  font-size: 0.75rem;
  color: var(--n-text-color-3);
}

.log-section {
  margin-top: 12px;
}

.log-section__title {
  margin: 0 0 8px;
  font-size: 0.875rem;
  font-weight: 600;
}

.log-section__hint {
  font-weight: 400;
  color: var(--n-text-color-3);
}

.log-section__text {
  margin: 0;
  font-size: 0.875rem;
  color: var(--n-text-color-2);
}

.candidate-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.candidate-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.candidate-row__label {
  min-width: 96px;
  font-weight: 500;
}

.candidate-row__score {
  min-width: 120px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.8125rem;
}

.log-desc :deep(.n-descriptions-table-content) {
  word-break: break-word;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.8125rem;
}
</style>
