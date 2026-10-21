<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NButton, NSpace, NAlert, NProgress, useMessage } from "naive-ui";
import { apiForm } from "@/api/client";
import type { EnrollmentOut, EnrollmentType } from "@/types/api";
import { ApiError } from "@/api/client";
import GuidedCaptureModal from "@/components/GuidedCaptureModal.vue";
import CameraCapture from "@/components/CameraCapture.vue";
import {
  PHOTO_CAPTURE_STEPS,
  MIN_PET_OBJECT_PHOTOS,
  type CaptureStepCopy,
} from "@/constants/captureSteps";

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

/** 0 intro, 1 tips, 2..capture steps, last complete */
const captureSteps = PHOTO_CAPTURE_STEPS;
const totalSteps = 2 + captureSteps.length + 1;
const step = ref(0);
const photoBlobs = ref<(Blob | null)[]>([]);
const uploading = ref(false);
const uploadDone = ref(false);

const isIntro = computed(() => step.value === 0);
const isTips = computed(() => step.value === 1);
const captureIndex = computed(() => step.value - 2);
const isCaptureStep = computed(
  () => step.value >= 2 && step.value < 2 + captureSteps.length,
);
const isDone = computed(() => step.value === totalSteps - 1);
const currentCapture = computed((): CaptureStepCopy | null => {
  const i = captureIndex.value;
  return i >= 0 && i < captureSteps.length ? captureSteps[i]! : null;
});

const capturedCount = computed(() => photoBlobs.value.filter(Boolean).length);

const wizardSteps = computed(() => {
  const items = [
    { title: "Intro", description: "Overview" },
    { title: "Tips", description: "Lighting" },
    ...captureSteps.map((s, i) => ({
      title: s.title,
      description: photoBlobs.value[i] ? "Captured" : undefined,
    })),
    { title: "Complete", description: uploadDone.value ? "Uploaded" : "Review" },
  ];
  return items;
});

function resetWizard() {
  step.value = 0;
  photoBlobs.value = captureSteps.map(() => null);
  uploading.value = false;
  uploadDone.value = false;
}

watch(
  () => props.show,
  (open) => {
    if (open) resetWizard();
  },
);

function close() {
  emit("update:show", false);
}

function onCapture(file: File) {
  const i = captureIndex.value;
  if (i < 0 || i >= captureSteps.length) return;
  const next = [...photoBlobs.value];
  next[i] = file;
  photoBlobs.value = next;
  message.success("Photo saved for this step");
}

async function uploadAll(): Promise<boolean> {
  const blobs = photoBlobs.value.filter((b): b is Blob => b != null);
  if (blobs.length < captureSteps.length) {
    message.warning("Complete each guided angle before finishing");
    return false;
  }

  uploading.value = true;
  try {
    const form = new FormData();
    const meta = blobs.map((_, i) => ({
      source: "photo_wizard",
      angle_id: captureSteps[i]?.id ?? `step-${i}`,
      angle_title: captureSteps[i]?.title,
      original_filename: `photo-${i + 1}.jpg`,
      content_type: "image/jpeg",
    }));
    form.append("sample_meta", JSON.stringify(meta));
    blobs.forEach((blob, i) => {
      form.append(
        "files",
        new File([blob], `photo-${i + 1}.jpg`, { type: blob.type || "image/jpeg" }),
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
  if (isIntro.value || isTips.value) {
    step.value += 1;
    return;
  }
  if (isCaptureStep.value) {
    const i = captureIndex.value;
    if (!photoBlobs.value[i]) {
      message.warning("Capture a photo for this step first");
      return;
    }
    if (i + 1 >= captureSteps.length) {
      step.value = totalSteps - 1;
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

const subjectNoun = computed(() =>
  props.enrollmentType === "pet" ? "pet" : "object",
);
</script>

<template>
  <GuidedCaptureModal
    :show="show"
    :title="`Photo enrollment — ${enrollmentLabel}`"
    :steps="wizardSteps"
    :current="step"
    @update:show="emit('update:show', $event)"
  >
    <div v-if="isIntro" class="step-body">
      <p class="lead">
        Guided photos help OpenRecognition match your
        <strong>{{ subjectNoun }}</strong> from different angles and lighting.
      </p>
      <p class="hint">
        We will walk through {{ captureSteps.length }} angles, then you can add extras until you
        have {{ MIN_PET_OBJECT_PHOTOS }}+ photos — add more from the enrollment page after this wizard.
      </p>
    </div>

    <div v-else-if="isTips" class="step-body">
      <ul class="tips">
        <li>Use natural light when possible — avoid heavy backlight.</li>
        <li>Vary distance and background across shots.</li>
        <li>Keep the subject in focus; blur reduces match quality.</li>
      </ul>
    </div>

    <div v-else-if="isCaptureStep && currentCapture" class="step-body">
      <p class="step-label">
        Angle {{ captureIndex + 1 }} of {{ captureSteps.length }} — {{ capturedCount }} captured
      </p>
      <p class="lead">{{ currentCapture.instruction }}</p>
      <CameraCapture
        :key="currentCapture.id"
        :hint="currentCapture.hint"
        :facing-mode="currentCapture.facingMode ?? 'environment'"
        @capture="onCapture"
      />
    </div>

    <div v-else-if="isDone" class="step-body">
      <NAlert v-if="uploadDone" type="success" title="Photos saved">
        Uploaded samples for <strong>{{ enrollmentLabel }}</strong>.
      </NAlert>
      <NAlert v-else-if="uploading" type="info" title="Uploading…" />
      <NAlert v-else type="warning" title="Upload incomplete">
        Retry upload or go back to fix missing angles.
      </NAlert>
      <NProgress
        v-if="uploadDone"
        type="line"
        :percentage="100"
        status="success"
        style="margin-top: 16px"
      />
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
            v-if="!isDone"
            type="primary"
            :loading="uploading"
            @click="next"
          >
            {{ isCaptureStep && captureIndex + 1 >= captureSteps.length ? "Finish & upload" : "Continue" }}
          </NButton>
          <NButton v-else-if="uploadDone" type="primary" @click="close">Done</NButton>
          <NButton v-else type="primary" :loading="uploading" @click="uploadAll">Retry upload</NButton>
        </NSpace>
      </NSpace>
    </template>
  </GuidedCaptureModal>
</template>

<style scoped>
.step-body {
  min-height: 200px;
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
</style>
