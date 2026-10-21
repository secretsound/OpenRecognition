<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NButton, NSpace, NAlert, NProgress, useMessage } from "naive-ui";
import { apiForm } from "@/api/client";
import type { EnrollmentOut } from "@/types/api";
import { ApiError } from "@/api/client";
import GuidedCaptureModal from "@/components/GuidedCaptureModal.vue";
import CameraCapture from "@/components/CameraCapture.vue";
import { FACE_CAPTURE_STEPS, type CaptureStepCopy } from "@/constants/captureSteps";

const props = defineProps<{
  show: boolean;
  enrollmentId: string;
  enrollmentLabel: string;
}>();

const emit = defineEmits<{
  "update:show": [value: boolean];
  completed: [enrollment: EnrollmentOut];
}>();

const message = useMessage();

const captureSteps = FACE_CAPTURE_STEPS;
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

const wizardSteps = computed(() => [
  { title: "Intro", description: "Overview" },
  { title: "Lighting", description: "Tips" },
  ...captureSteps.map((s, i) => ({
    title: s.title,
    description: photoBlobs.value[i] ? "Captured" : undefined,
  })),
  { title: "Complete", description: uploadDone.value ? "Uploaded" : "Review" },
]);

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
  message.success("Face photo saved");
}

async function uploadAll(): Promise<boolean> {
  const blobs = photoBlobs.value.filter((b): b is Blob => b != null);
  if (blobs.length < captureSteps.length) {
    message.warning("Complete each angle before finishing");
    return false;
  }

  uploading.value = true;
  try {
    const form = new FormData();
    const meta = blobs.map((_, i) => ({
      source: "face_wizard",
      angle_id: captureSteps[i]?.id ?? `step-${i}`,
      angle_title: captureSteps[i]?.title,
      original_filename: `face-${i + 1}.jpg`,
      content_type: "image/jpeg",
    }));
    form.append("sample_meta", JSON.stringify(meta));
    blobs.forEach((blob, i) => {
      form.append(
        "files",
        new File([blob], `face-${i + 1}.jpg`, { type: blob.type || "image/jpeg" }),
      );
    });
    const updated = await apiForm<EnrollmentOut>(
      `/v1/enrollments/${props.enrollmentId}/samples`,
      form,
    );
    uploadDone.value = true;
    emit("completed", updated);
    message.success("Face photos uploaded");
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
    if (!photoBlobs.value[captureIndex.value]) {
      message.warning("Capture a photo for this step first");
      return;
    }
    if (captureIndex.value + 1 >= captureSteps.length) {
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
</script>

<template>
  <GuidedCaptureModal
    :show="show"
    :title="`Face enrollment — ${enrollmentLabel}`"
    :steps="wizardSteps"
    :current="step"
    @update:show="emit('update:show', $event)"
  >
    <div v-if="isIntro" class="step-body">
      <p class="lead">
        Capture <strong>{{ captureSteps.length }} face angles</strong> so recognition works from
        different viewpoints.
      </p>
      <p class="hint">Photos stay on this device until you finish the wizard.</p>
    </div>

    <div v-else-if="isTips" class="step-body">
      <ul class="tips">
        <li>Face the light source — avoid standing with a window behind you.</li>
        <li>Remove sunglasses or heavy shadows on the face.</li>
        <li>Use the front camera and hold the device at eye level.</li>
      </ul>
    </div>

    <div v-else-if="isCaptureStep && currentCapture" class="step-body">
      <p class="step-label">Angle {{ captureIndex + 1 }} of {{ captureSteps.length }}</p>
      <p class="lead">{{ currentCapture.instruction }}</p>
      <CameraCapture
        :key="currentCapture.id"
        :facing-mode="currentCapture.facingMode ?? 'user'"
        @capture="onCapture"
      />
    </div>

    <div v-else-if="isDone" class="step-body">
      <NAlert v-if="uploadDone" type="success" title="Face photos saved">
        Uploaded for <strong>{{ enrollmentLabel }}</strong>.
      </NAlert>
      <NAlert v-else-if="uploading" type="info" title="Uploading…" />
      <NAlert v-else type="warning" title="Upload incomplete" />
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
          <NButton v-if="!isDone" type="primary" :loading="uploading" @click="next">
            {{
              isCaptureStep && captureIndex + 1 >= captureSteps.length
                ? "Finish & upload"
                : "Continue"
            }}
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
