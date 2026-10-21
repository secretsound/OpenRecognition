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
  NCollapse,
  NCollapseItem,
  NAlert,
  useMessage,
} from "naive-ui";
import type { SelectOption } from "naive-ui";
import AppPageHeader from "@/components/AppPageHeader.vue";
import AudioTestSource from "@/components/AudioTestSource.vue";
import ImageTestSource from "@/components/ImageTestSource.vue";
import VideoTestSource from "@/components/VideoTestSource.vue";
import RecognizeResults from "@/components/RecognizeResults.vue";
import { recognizeFile } from "@/api/recognize";
import type { RecognizeResponse } from "@/types/api";
import { ApiError } from "@/api/client";
import { videoModalitiesParam, type VideoModalityChoice } from "@/utils/videoClip";

const route = useRoute();
const router = useRouter();
const message = useMessage();

const modality = ref<"audio" | "image" | "video">("audio");
const audioTestFile = ref<File | null>(null);
const imageTestFile = ref<File | null>(null);
const videoTestFile = ref<File | null>(null);
const videoTestSourceRef = ref<InstanceType<typeof VideoTestSource> | null>(null);
const running = ref(false);
const result = ref<RecognizeResponse | null>(null);

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

const expectationMet = computed(() => {
  if (!expectedLabel.value || !result.value) return null;
  const known = result.value.entities.filter((e) => e.label !== "unknown");
  if (known.length === 0) return false;
  const top = [...known].sort((a, b) => b.confidence - a.confidence)[0];
  return (
    top.label.toLowerCase() === expectedLabel.value.toLowerCase() &&
    top.confidence >= minConfidence.value
  );
});

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
  if (modality.value === "audio") return audioTestFile.value != null;
  if (modality.value === "image") return imageTestFile.value != null;
  return videoTestFile.value != null;
});

const initialModality = route.query.modality;
if (initialModality === "audio" || initialModality === "image" || initialModality === "video") {
  modality.value = initialModality;
}

async function runTest() {
  let file: File | null = null;
  if (modality.value === "audio") file = audioTestFile.value;
  else if (modality.value === "image") file = imageTestFile.value;
  else file = videoTestFile.value;

  if (!file) {
    message.warning(
      modality.value === "audio"
        ? "Upload or record audio to test"
        : modality.value === "image"
          ? "Upload or capture an image to test"
          : "Extract a video clip to test",
    );
    return;
  }

  running.value = true;
  result.value = null;
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
    result.value = await recognizeFile<RecognizeResponse>(path, file, params);

    if (enrollmentIdFromQuery.value) {
      sessionStorage.setItem(`or-tested-${enrollmentIdFromQuery.value}`, "1");
    }
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Recognition failed");
  } finally {
    running.value = false;
  }
}
</script>

<template>
  <div class="try-match">
    <AppPageHeader
      title="Try a match"
      :description="
        expectedLabel
          ? `See whether this matches ${expectedLabel}.`
          : 'Check a voice, photo, or video against the library.'
      "
    >
      <template #action>
        <NButton type="primary" :loading="running" :disabled="!hasTestInput" @click="runTest">
          Run
        </NButton>
      </template>
    </AppPageHeader>

    <NAlert
      v-if="result && expectedLabel && expectationMet !== null"
      :type="expectationMet ? 'success' : 'warning'"
      :bordered="false"
    >
      {{
        expectationMet
          ? `This matches ${expectedLabel}.`
          : `This does not match ${expectedLabel}. Try another clip, or add a sample and run it again.`
      }}
    </NAlert>

    <div class="kind-grid" role="group" aria-label="What to match">
      <button
        type="button"
        class="or-choice-card"
        :class="{ 'is-selected': modality === 'audio' }"
        @click="modality = 'audio'"
      >
        <span class="or-choice-card__title">Voice</span>
        <span class="or-choice-card__desc">A spoken clip, checked against people and sounds.</span>
      </button>
      <button
        type="button"
        class="or-choice-card"
        :class="{ 'is-selected': modality === 'image' }"
        @click="modality = 'image'"
      >
        <span class="or-choice-card__title">Photo</span>
        <span class="or-choice-card__desc">A still photo, checked against faces, pets, and objects.</span>
      </button>
      <button
        type="button"
        class="or-choice-card"
        :class="{ 'is-selected': modality === 'video' }"
        @click="modality = 'video'"
      >
        <span class="or-choice-card__title">Video</span>
        <span class="or-choice-card__desc">A short clip. Trim it, then check faces and voices.</span>
      </button>
    </div>

    <AudioTestSource v-if="modality === 'audio'" v-model="audioTestFile" />
    <ImageTestSource v-else-if="modality === 'image'" v-model="imageTestFile" />
    <VideoTestSource v-else ref="videoTestSourceRef" v-model="videoTestFile" />

    <NCollapse>
      <NCollapseItem title="Advanced" name="advanced">
        <NForm label-placement="top">
          <NFormItem v-if="modality === 'audio'" label="Audio mode">
            <NSelect v-model:value="audioMode" :options="audioModeOptions" />
          </NFormItem>
          <p v-if="modality === 'audio'" class="field-hint">
            Full checks that the clip is speech and then who is speaking. Speech check only skips the name.
          </p>
          <NFormItem :label="`Minimum confidence (${Math.round(minConfidence * 100)}%)`">
            <NSlider v-model:value="minConfidence" :min="0.3" :max="0.99" :step="0.01" />
          </NFormItem>
          <NFormItem label="Practice run">
            <NSwitch v-model:value="dryRun" />
          </NFormItem>
          <p class="field-hint">A practice run does not notify Connections.</p>
        </NForm>
      </NCollapseItem>
    </NCollapse>

    <section v-if="result" class="result-block">
      <h2 class="result-title">Result</h2>
      <RecognizeResults
        :result="result"
        :expected-label="expectedLabel"
        :min-confidence="minConfidence"
      />
    </section>
  </div>
</template>

<style scoped>
.try-match {
  display: flex;
  flex-direction: column;
  gap: var(--or-section-gap);
}

.try-match :deep(.app-page-header) {
  margin-bottom: 0;
}

.kind-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--or-inline-gap);
}

@media (max-width: 768px) {
  .kind-grid {
    grid-template-columns: 1fr;
  }
}

.field-hint {
  margin: -8px 0 16px;
  color: var(--n-text-color-3);
  font-size: 0.8125rem;
  line-height: 1.45;
}

.result-title {
  margin: 0 0 8px;
  font-size: 1rem;
  font-weight: 600;
}
</style>
