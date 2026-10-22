<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NButton, NSpace, NAlert, NSpin, useMessage } from "naive-ui";
import { api, apiForm, ApiError } from "@/api/client";
import type { EnrollmentOut, EnrollmentType, SampleOut, SamplePreviewOut } from "@/types/api";
import GuidedCaptureModal from "@/components/GuidedCaptureModal.vue";
import CameraCapture from "@/components/CameraCapture.vue";
import ConfidenceMeter from "@/components/kit/ConfidenceMeter.vue";
import {
  MIN_PET_OBJECT_PHOTOS,
  PHOTO_CAPTURE_BANK,
  pickPhotoSteps,
  type CaptureSessionMode,
  type CaptureStepCopy,
} from "@/constants/captureSteps";
import {
  analyzePhotoLocally,
  mergePhotoQuality,
  photoIssueLabel,
} from "@/utils/photoQuality";
import type { TakeQuality } from "@/utils/takeQuality";

const props = defineProps<{
  show: boolean;
  enrollmentId: string;
  enrollmentLabel: string;
  enrollmentType: EnrollmentType;
}>();

const emit = defineEmits<{
  "update:show": [value: boolean];
  completed: [enrollment: EnrollmentOut];
}>();

const message = useMessage();
const cameraRef = ref<InstanceType<typeof CameraCapture> | null>(null);

const captureSteps = ref<CaptureStepCopy[]>(PHOTO_CAPTURE_BANK.slice(0, 6));
const sessionMode = ref<CaptureSessionMode>("core");
const loadingSession = ref(false);
const step = ref(0);
const photoBlobs = ref<(Blob | null)[]>([]);
const photoQuality = ref<(TakeQuality | null)[]>([]);
const scoringTake = ref(false);
const uploading = ref(false);
const uploadDone = ref(false);
let takeSeq = 0;

const subjectNoun = computed(() => (props.enrollmentType === "pet" ? "pet" : "object"));
const totalSteps = computed(() => 1 + captureSteps.value.length + 1);
const isIntro = computed(() => step.value === 0);
const captureIndex = computed(() => step.value - 1);
const isCaptureStep = computed(
  () => step.value >= 1 && step.value < 1 + captureSteps.value.length,
);
const isDone = computed(() => step.value === totalSteps.value - 1);
const currentCapture = computed((): CaptureStepCopy | null => {
  const i = captureIndex.value;
  return i >= 0 && i < captureSteps.value.length ? captureSteps.value[i]! : null;
});
const currentQuality = computed(() => {
  const i = captureIndex.value;
  return i >= 0 ? photoQuality.value[i] ?? null : null;
});
const weakTakes = computed(() =>
  photoQuality.value
    .map((q, i) => ({ i, q }))
    .filter((row): row is { i: number; q: TakeQuality } => row.q?.verdict === "retry"),
);

const wizardSteps = computed(() => [
  { title: "Intro", description: "How it works" },
  ...captureSteps.value.map((s, i) => ({
    title: s.title,
    description:
      photoQuality.value[i]?.verdict === "retry"
        ? "Redo"
        : photoBlobs.value[i]
          ? "Captured"
          : undefined,
  })),
  { title: "Complete", description: uploadDone.value ? "Uploaded" : "Review" },
]);

function emptySlots() {
  return Array.from({ length: captureSteps.value.length }, () => null);
}

function resetWizard() {
  step.value = 0;
  photoBlobs.value = emptySlots();
  photoQuality.value = emptySlots();
  uploading.value = false;
  uploadDone.value = false;
  scoringTake.value = false;
}

async function loadSession() {
  loadingSession.value = true;
  try {
    const samples = await api<SampleOut[]>(`/v1/enrollments/${props.enrollmentId}/samples`);
    const used = samples
      .filter((s) => s.modality === "image")
      .map((s) => s.phrase_text || "")
      .filter(Boolean);
    const picked = pickPhotoSteps(used);
    captureSteps.value = picked.steps;
    sessionMode.value = picked.mode;
  } catch {
    const picked = pickPhotoSteps([]);
    captureSteps.value = picked.steps;
    sessionMode.value = picked.mode;
  } finally {
    photoBlobs.value = emptySlots();
    photoQuality.value = emptySlots();
    loadingSession.value = false;
  }
}

watch(
  () => props.show,
  (open) => {
    if (open) {
      resetWizard();
      void loadSession();
    } else {
      cameraRef.value?.stopCamera();
    }
  },
);

watch(captureIndex, () => {
  cameraRef.value?.discardPending();
});

function close() {
  emit("update:show", false);
}

function setQuality(index: number, quality: TakeQuality | null) {
  const next = [...photoQuality.value];
  while (next.length <= index) next.push(null);
  next[index] = quality;
  photoQuality.value = next;
}

async function scorePhoto(index: number, blob: Blob) {
  const seq = ++takeSeq;
  scoringTake.value = true;
  try {
    const local = await analyzePhotoLocally(blob);
    if (seq !== takeSeq) return;
    setQuality(index, local);
    const form = new FormData();
    form.append("file", new File([blob], "take.jpg", { type: blob.type || "image/jpeg" }));
    const remote = await apiForm<SamplePreviewOut>(
      `/v1/enrollments/${props.enrollmentId}/samples/preview`,
      form,
    );
    if (seq !== takeSeq) return;
    setQuality(index, mergePhotoQuality(local, remote, "photo"));
  } catch {
    /* Local score is enough if preview fails. */
  } finally {
    if (seq === takeSeq) scoringTake.value = false;
  }
}

async function onCapture(file: File) {
  const i = captureIndex.value;
  if (i < 0 || i >= captureSteps.value.length) return;
  const next = [...photoBlobs.value];
  next[i] = file;
  photoBlobs.value = next;
  setQuality(i, null);

  const last = i + 1 >= captureSteps.value.length;
  if (last) {
    await scorePhoto(i, file);
    step.value = totalSteps.value - 1;
    if (photoQuality.value.some((q) => q?.verdict === "retry")) {
      message.warning("Some photos scored low. Retake them or upload anyway.");
      return;
    }
    await uploadAll();
    return;
  }

  void scorePhoto(i, file);
  step.value += 1;
}

async function uploadAll(): Promise<boolean> {
  const blobs = photoBlobs.value.filter((b): b is Blob => b != null);
  if (blobs.length < captureSteps.value.length) {
    message.warning("Capture each angle before finishing");
    return false;
  }
  uploading.value = true;
  try {
    const form = new FormData();
    const meta = captureSteps.value.map((s) => ({
      source: "photo_wizard",
      phrase_text: s.id,
      original_filename: `photo-${s.id}.jpg`,
      content_type: "image/jpeg",
    }));
    form.append("sample_meta", JSON.stringify(meta));
    blobs.forEach((blob, i) => {
      const id = captureSteps.value[i]?.id ?? String(i + 1);
      form.append(
        "files",
        new File([blob], `photo-${id}.jpg`, { type: blob.type || "image/jpeg" }),
      );
    });
    const updated = await apiForm<EnrollmentOut>(
      `/v1/enrollments/${props.enrollmentId}/samples`,
      form,
    );
    uploadDone.value = true;
    emit("completed", updated);
    message.success("Photos uploaded");
    return true;
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Upload failed");
    return false;
  } finally {
    uploading.value = false;
  }
}

async function next() {
  if (isIntro.value) {
    step.value = 1;
    return;
  }
  if (isCaptureStep.value) {
    if (!photoBlobs.value[captureIndex.value]) {
      message.warning("Capture a photo for this step first");
      return;
    }
    if (captureIndex.value + 1 >= captureSteps.value.length) {
      step.value = totalSteps.value - 1;
      if (weakTakes.value.length || currentQuality.value?.verdict === "retry") {
        message.warning("Some photos scored low. Retake them or upload anyway.");
        return;
      }
      await uploadAll();
    } else {
      step.value += 1;
    }
    return;
  }
  close();
}

function back() {
  if (step.value > 0) step.value -= 1;
}
</script>

<template>
  <GuidedCaptureModal
    :show="show"
    :title="`Photo training — ${enrollmentLabel}`"
    :steps="wizardSteps"
    :current="step"
    layout="progress"
    @update:show="emit('update:show', $event)"
  >
    <div v-if="loadingSession" class="step-body step-body--center">
      <NSpin size="small" />
      <p class="hint">Choosing angles you have not captured yet…</p>
    </div>

    <div v-else-if="isIntro" class="step-body">
      <p class="lead">
        {{
          sessionMode === "improve"
            ? `These ${captureSteps.length} shots cover new angles of this ${subjectNoun}.`
            : `Walk around this ${subjectNoun} — front, sides, close, and from farther back.`
        }}
      </p>
      <ul class="tips">
        <li>Use the rear camera. Natural light is better than a flash.</li>
        <li>Keep the subject sharp. Blur is the usual reason matches fail.</li>
        <li>
          {{ MIN_PET_OBJECT_PHOTOS }}+ photos is the sweet spot. You can add more after this set.
        </li>
      </ul>
    </div>

    <div v-else-if="isCaptureStep && currentCapture" class="step-body">
      <p class="step-label">Photo {{ captureIndex + 1 }} of {{ captureSteps.length }}</p>
      <p class="delivery-title">{{ currentCapture.title }}</p>
      <p class="lead">{{ currentCapture.instruction }}</p>
      <CameraCapture
        ref="cameraRef"
        autostart
        facing-mode="environment"
        capture-label="Capture"
        :hint="currentCapture.instruction"
        :max-height="260"
        @capture="onCapture"
      />
      <div
        v-if="photoBlobs[captureIndex] || scoringTake || currentQuality"
        class="take-score"
        :class="currentQuality ? `take-score--${currentQuality.verdict}` : ''"
      >
        <div class="take-score__head">
          <p class="or-caps">This photo</p>
          <span v-if="scoringTake" class="or-muted or-small">Checking…</span>
          <span v-else-if="currentQuality" class="or-muted or-small">
            {{ currentQuality.verdict === "keep" ? "Looks good" : "Retake this one" }}
          </span>
        </div>
        <ConfidenceMeter
          v-if="currentQuality"
          :value="currentQuality.score"
          :threshold="0.55"
          size="sm"
        />
        <p v-if="currentQuality" class="take-score__advice">{{ currentQuality.advice }}</p>
        <ul v-if="currentQuality?.issues.length" class="take-score__issues">
          <li v-for="issue in currentQuality.issues" :key="issue">{{ photoIssueLabel(issue) }}</li>
        </ul>
      </div>
    </div>

    <div v-else-if="isDone" class="step-body">
      <NAlert v-if="uploadDone" type="success" title="Photos saved">
        Uploaded for <strong>{{ enrollmentLabel }}</strong>.
      </NAlert>
      <NAlert v-else-if="uploading" type="info" title="Uploading…" />
      <NAlert
        v-else-if="weakTakes.length"
        type="warning"
        title="Some photos should be taken again"
      >
        Shots {{ weakTakes.map((row) => row.i + 1).join(", ") }} scored low.
      </NAlert>
      <NAlert v-else type="warning" title="Upload incomplete" />
    </div>

    <template #footer>
      <NSpace justify="space-between" style="width: 100%">
        <NButton v-if="step > 0 && !isDone" quaternary :disabled="uploading" @click="back">
          Back
        </NButton>
        <span v-else />
        <NSpace>
          <NButton :disabled="uploading" @click="close">
            {{ isDone && uploadDone ? "Close" : "Cancel" }}
          </NButton>
          <NButton
            v-if="!isDone && (!isCaptureStep || photoBlobs[captureIndex])"
            type="primary"
            :loading="uploading"
            @click="next"
          >
            {{
              isCaptureStep && captureIndex + 1 >= captureSteps.length
                ? "Finish & upload"
                : "Continue"
            }}
          </NButton>
          <NButton v-else-if="uploadDone" type="primary" @click="close">Done</NButton>
          <NButton v-else type="primary" :loading="uploading" @click="uploadAll">
            {{ weakTakes.length ? "Upload anyway" : "Retry upload" }}
          </NButton>
        </NSpace>
      </NSpace>
    </template>
  </GuidedCaptureModal>
</template>

<style scoped>
.step-body {
  min-height: 200px;
}

.step-body--center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.lead {
  margin: 0 0 12px;
  line-height: 1.55;
}

.hint,
.tips {
  color: var(--n-text-color-3);
  font-size: 0.9rem;
  line-height: 1.55;
}

.tips {
  margin: 0;
  padding-left: 1.25rem;
}

.step-label {
  margin: 0 0 8px;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--n-text-color-3);
}

.delivery-title {
  margin: 0 0 8px;
  font-size: 0.95rem;
  font-weight: 600;
}

.take-score {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: var(--or-radius-md);
  border: 1px solid var(--or-line);
}

.take-score--keep {
  border-color: color-mix(in oklab, var(--n-success-color) 45%, var(--or-line));
}

.take-score--retry {
  border-color: color-mix(in oklab, var(--n-warning-color) 55%, var(--or-line));
}

.take-score__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.take-score__advice {
  margin: 8px 0 0;
  font-size: 0.85rem;
}

.take-score__issues {
  margin: 8px 0 0;
  padding-left: 1.1rem;
  font-size: 0.8rem;
  color: var(--n-text-color-3);
}
</style>
