<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NForm,
  NFormItem,
  NSelect,
  NSlider,
  NSwitch,
  NAlert,
  useMessage,
} from "naive-ui";
import type { SelectOption } from "naive-ui";
import PageHeader from "@/components/kit/PageHeader.vue";
import SegmentedControl from "@/components/kit/SegmentedControl.vue";
import ProfileMark from "@/components/kit/ProfileMark.vue";
import ConfidenceMeter from "@/components/kit/ConfidenceMeter.vue";
import Chip from "@/components/kit/Chip.vue";
import AudioTestSource from "@/components/AudioTestSource.vue";
import ImageTestSource from "@/components/ImageTestSource.vue";
import VideoTestSource from "@/components/VideoTestSource.vue";
import { createVideoJob, pollJob, recognizeFile } from "@/api/recognize";
import { apiForm, ApiError } from "@/api/client";
import type { EnrollmentOut, RecognizeResponse } from "@/types/api";
import {
  DEFAULT_VIDEO_LIMITS,
  videoModalitiesParam,
  type VideoModalityChoice,
} from "@/utils/videoClip";
import { verdictFromRecognize } from "@/utils/verdict";
import { pct } from "@/utils/confidence";

const route = useRoute();
const router = useRouter();
const message = useMessage();

const modality = ref<"audio" | "image" | "video">("audio");
const audioTestFile = ref<File | null>(null);
const imageTestFile = ref<File | null>(null);
const videoTestFile = ref<File | null>(null);
const videoTestSourceRef = ref<InstanceType<typeof VideoTestSource> | null>(null);
const running = ref(false);
const listening = ref(false);
const jobStatus = ref<string | null>(null);
const savingSample = ref(false);
const result = ref<RecognizeResponse | null>(null);
const showOptions = ref(false);
const showDetails = ref(false);

const audioMode = ref("full");
const minConfidence = ref(0.75);
const dryRun = ref(true);

const expectedLabel = computed(() => {
  const q = route.query.expect;
  return typeof q === "string" ? q : null;
});

const enrollmentIdFromQuery = computed(() => {
  const q = route.query.enrollmentId;
  return typeof q === "string" ? q : null;
});

const audioModeOptions: SelectOption[] = [
  { label: "Full — check that it is speech, then name the speaker", value: "full" },
  { label: "Identify — name the speaker without the speech check", value: "identify" },
  { label: "Speech check only — do not name anyone", value: "gate" },
];

const modalityOptions = [
  { value: "audio" as const, label: "Voice", hint: "A spoken clip" },
  { value: "image" as const, label: "Photo", hint: "A still photo" },
  { value: "video" as const, label: "Video", hint: "A short clip" },
];

watch(modality, (next) => {
  audioTestFile.value = null;
  imageTestFile.value = null;
  videoTestFile.value = null;
  result.value = null;
  if (route.query.modality === next) return;
  router.replace({ query: { ...route.query, modality: next } });
});

watch(
  () => route.query.modality,
  (m) => {
    if ((m === "audio" || m === "image" || m === "video") && modality.value !== m) {
      modality.value = m;
    }
  },
);

const hasTestInput = computed(() => {
  if (modality.value === "audio") return audioTestFile.value != null || listening.value;
  if (modality.value === "image") return imageTestFile.value != null;
  return videoTestFile.value != null;
});

const initialModality = route.query.modality;
if (initialModality === "audio" || initialModality === "image" || initialModality === "video") {
  modality.value = initialModality;
}

const verdict = computed(() =>
  result.value ? verdictFromRecognize(result.value, { minConfidence: minConfidence.value }) : null,
);

const lastCurl = ref("");

function buildCurl(path: string, file: File, params: Record<string, string | number | boolean>) {
  const flags = Object.entries(params)
    .map(([k, v]) => `-F ${k}=${v}`)
    .join(" ");
  return `curl -sS ${path} ${flags} -F file=@${file.name}`;
}

async function runTest(opts?: { silent?: boolean }) {
  let file: File | null = null;
  if (modality.value === "audio") file = audioTestFile.value;
  else if (modality.value === "image") file = imageTestFile.value;
  else file = videoTestFile.value;

  if (!file) {
    if (!opts?.silent) {
      message.warning(
        modality.value === "audio"
          ? "Upload, record, or listen to test"
          : modality.value === "image"
            ? "Upload or capture an image to test"
            : "Extract a video clip to test",
      );
    }
    return;
  }

  running.value = true;
  jobStatus.value = null;
  if (!opts?.silent) result.value = null;
  try {
    const params: Record<string, string | number | boolean> = {
      dry_run: dryRun.value,
      min_confidence: minConfidence.value,
      return_unknown: true,
      include_candidates: true,
    };
    let path = "/v1/recognize/image";
    if (modality.value === "audio") {
      path = "/v1/recognize/audio";
      params.mode = audioMode.value;
    } else if (modality.value === "video") {
      path = "/v1/recognize/video";
      const mod = videoTestSourceRef.value?.getModality() ?? "both";
      params.video_modalities = videoModalitiesParam(mod as VideoModalityChoice);
    }

    const clipSec = videoTestSourceRef.value?.getClipDuration?.() ?? 0;
    const useJob =
      modality.value === "video" && clipSec > DEFAULT_VIDEO_LIMITS.recognize_sync_max_sec;

    if (useJob) {
      jobStatus.value = "Working on a longer clip…";
      lastCurl.value = buildCurl("/v1/jobs", file, params);
      const job = await createVideoJob(file, params);
      jobStatus.value = "Still working…";
      result.value = await pollJob(job.id);
    } else {
      lastCurl.value = buildCurl(path, file, params);
      result.value = await recognizeFile<RecognizeResponse>(path, file, params);
    }

    if (enrollmentIdFromQuery.value) {
      sessionStorage.setItem(`or-tested-${enrollmentIdFromQuery.value}`, "1");
    }
  } catch (e) {
    if (!opts?.silent) {
      message.error(e instanceof ApiError ? e.message : "Recognition failed");
    }
  } finally {
    running.value = false;
    jobStatus.value = null;
  }
}

function onListenWindow(next: File) {
  audioTestFile.value = next;
  if (running.value) return;
  void runTest({ silent: true });
}

async function saveAsSample() {
  const id = enrollmentIdFromQuery.value ?? verdict.value?.entityId;
  const file =
    modality.value === "audio"
      ? audioTestFile.value
      : modality.value === "image"
        ? imageTestFile.value
        : videoTestFile.value;
  if (!id || !file) {
    message.warning("Open Recognize from a profile to save a sample, or match someone first.");
    return;
  }
  savingSample.value = true;
  try {
    const form = new FormData();
    form.append("files", file);
    await apiForm<EnrollmentOut>(`/v1/enrollments/${id}/samples`, form);
    message.success("Saved as a sample");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not save the sample");
  } finally {
    savingSample.value = false;
  }
}

async function copyCurl() {
  if (!lastCurl.value) return;
  try {
    await navigator.clipboard.writeText(lastCurl.value);
    message.success("Copied curl");
  } catch {
    message.error("Could not copy");
  }
}

const candidates = computed(() => {
  const list = result.value?.diagnostics?.candidates ?? [];
  return [...list].sort((a, b) => b.confidence - a.confidence);
});
</script>

<template>
  <div class="or-page">
    <PageHeader
      title="Recognize"
      :description="
        expectedLabel
          ? `Checking whether this is ${expectedLabel}.`
          : 'Check a voice, photo, or video against the library.'
      "
    >
      <template #action>
        <NButton type="primary" :loading="running" :disabled="!hasTestInput || listening" @click="() => runTest()">
          {{ listening ? "Listening" : "Run" }}
        </NButton>
      </template>
    </PageHeader>

    <div class="recognize-grid">
      <section class="recognize-input or-stack">
        <SegmentedControl v-model="modality" aria-label="What to match" :options="modalityOptions" />

        <AudioTestSource
          v-if="modality === 'audio'"
          v-model="audioTestFile"
          @window="onListenWindow"
          @listening="listening = $event"
        />
        <ImageTestSource v-else-if="modality === 'image'" v-model="imageTestFile" />
        <VideoTestSource v-else ref="videoTestSourceRef" v-model="videoTestFile" />

        <div class="run-row">
          <NButton type="primary" :loading="running" :disabled="!hasTestInput || listening" @click="() => runTest()">
            {{ listening ? "Listening" : "Run" }}
          </NButton>
          <NButton quaternary @click="showOptions = !showOptions">
            {{ showOptions ? "Hide options" : "Options" }}
          </NButton>
        </div>

        <div v-if="showOptions" class="or-surface or-surface--sm">
          <NForm label-placement="top">
            <NFormItem v-if="modality === 'audio'" label="Audio mode">
              <NSelect v-model:value="audioMode" :options="audioModeOptions" />
            </NFormItem>
            <NFormItem :label="`Minimum confidence (${Math.round(minConfidence * 100)}%)`">
              <NSlider v-model:value="minConfidence" :min="0.3" :max="0.99" :step="0.01" />
            </NFormItem>
            <NFormItem label="Practice run">
              <NSwitch v-model:value="dryRun" />
            </NFormItem>
            <p class="or-muted or-small">A practice run does not notify Connections.</p>
          </NForm>
        </div>
      </section>

      <section class="recognize-result">
        <div v-if="!result" class="result-placeholder or-surface or-surface--md">
          <p class="or-caps">Result</p>
          <p v-if="jobStatus" class="or-muted">{{ jobStatus }}</p>
          <p v-else-if="listening" class="or-muted">Listening. A verdict will land here when we hear speech.</p>
          <p v-else class="or-muted">Run a clip or photo. The verdict lands here.</p>
        </div>
        <div v-else class="or-stack">
          <article class="verdict or-surface or-surface--md" :class="`verdict--${verdict?.kind}`">
            <div class="verdict__who">
              <ProfileMark
                v-if="verdict?.label"
                :label="verdict.label"
                :type="verdict.type ?? undefined"
                size="lg"
              />
              <div>
                <p class="or-caps">{{ verdict?.kind === "match" ? "This matches" : "Verdict" }}</p>
                <h2 class="or-heading">{{ verdict?.sentence }}</h2>
              </div>
            </div>
            <ConfidenceMeter
              v-if="verdict?.confidence != null"
              :value="verdict.confidence"
              :threshold="verdict.threshold"
              size="lg"
            />
            <div class="verdict__actions">
              <NButton
                v-if="verdict?.entityId"
                text
                type="primary"
                @click="router.push(`/enrollments/${verdict.entityId}`)"
              >
                Open profile
              </NButton>
              <NButton
                v-if="verdict?.kind === 'match'"
                text
                :loading="savingSample"
                @click="saveAsSample"
              >
                Save this as a sample
              </NButton>
              <NButton v-if="lastCurl" text @click="copyCurl">Copy as curl</NButton>
            </div>
          </article>

          <div v-if="candidates.length" class="or-surface or-surface--sm">
            <p class="or-caps" style="margin-bottom: 10px">Candidates</p>
            <ul class="cand-list">
              <li v-for="row in candidates" :key="row.entity_id">
                <ProfileMark :label="row.label" :type="row.type" size="sm" />
                <span class="cand-list__name">{{ row.label }}</span>
                <Chip :tone="row.accepted ? 'success' : 'default'">
                  {{ row.accepted ? "Would match" : "Below" }}
                </Chip>
                <ConfidenceMeter
                  :value="row.confidence"
                  :threshold="row.threshold_used ?? minConfidence"
                  size="sm"
                />
              </li>
            </ul>
          </div>

          <button type="button" class="details-toggle" @click="showDetails = !showDetails">
            {{ showDetails ? "Hide details" : "Details" }}
          </button>
          <div v-if="showDetails" class="or-surface or-surface--sm or-stack">
            <p v-if="result.gate" class="or-small">
              Speech check: <strong>{{ result.gate }}</strong>
              <span v-if="result.reason"> — {{ result.reason }}</span>
            </p>
            <p v-if="result.diagnostics?.pipelines.length" class="or-small or-muted">
              Pipelines: {{ result.diagnostics.pipelines.join(", ") }}
            </p>
            <p class="or-small or-muted">
              {{ result.meta.latency_ms.toFixed(0) }} ms
              <span v-if="result.meta.dry_run"> · practice</span>
              <span v-if="result.meta.request_id"> · {{ result.meta.request_id }}</span>
            </p>
            <ul v-if="result.diagnostics?.notes.length" class="or-muted or-small">
              <li v-for="(note, i) in result.diagnostics.notes" :key="i">{{ note }}</li>
            </ul>
            <p v-if="result.entities.length" class="or-small or-muted">
              API returned
              {{ result.entities.map((e) => `${e.label} ${pct(e.confidence)}`).join(" · ") }}
            </p>
          </div>
        </div>
      </section>
    </div>

    <NAlert
      v-if="result && expectedLabel && verdict"
      :type="verdict.kind === 'match' && verdict.label?.toLowerCase() === expectedLabel.toLowerCase() ? 'success' : 'warning'"
      :bordered="false"
    >
      {{
        verdict.kind === "match" && verdict.label?.toLowerCase() === expectedLabel.toLowerCase()
          ? `This matches ${expectedLabel}.`
          : `This does not match ${expectedLabel}. Try another clip, or add a sample and run it again.`
      }}
    </NAlert>
  </div>
</template>

<style scoped>
.recognize-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--or-space-6);
  align-items: start;
}

.recognize-result {
  position: sticky;
  top: var(--or-space-4);
}

.result-placeholder {
  min-height: 180px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}

.run-row {
  display: flex;
  align-items: center;
  gap: var(--or-space-2);
}

.verdict__who {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 16px;
}

.verdict__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.verdict--match {
  background: color-mix(in oklab, var(--or-success) 8%, var(--or-surface));
}

.cand-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cand-list li {
  display: grid;
  grid-template-columns: auto 1fr auto minmax(90px, 140px);
  align-items: center;
  gap: 8px;
}

.cand-list__name {
  font-weight: 500;
}

.details-toggle {
  appearance: none;
  border: 0;
  background: none;
  color: var(--or-accent);
  font: inherit;
  font-weight: 500;
  cursor: pointer;
  padding: 0;
  text-align: left;
}

@media (max-width: 1199px) {
  .recognize-grid {
    grid-template-columns: 1fr;
  }

  .recognize-result {
    position: static;
  }
}

@media (max-width: 639px) {
  .cand-list li {
    grid-template-columns: auto 1fr;
  }
}
</style>
