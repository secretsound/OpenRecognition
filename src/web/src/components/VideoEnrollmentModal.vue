<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NAlert, NButton, NSpace, useMessage } from "naive-ui";
import GuidedCaptureModal from "@/components/GuidedCaptureModal.vue";
import VideoClipper from "@/components/VideoClipper.vue";
import { apiForm } from "@/api/client";
import type { EnrollmentOut, EnrollmentType } from "@/types/api";
import { ApiError } from "@/api/client";
import {
  DEFAULT_VIDEO_LIMITS,
  type VideoModalityChoice,
  videoModalitiesParam,
} from "@/utils/videoClip";

const props = defineProps<{
  enrollmentId: string;
  enrollmentLabel: string;
  enrollmentType: EnrollmentType;
}>();

const show = defineModel<boolean>("show", { required: true });

const emit = defineEmits<{
  completed: [enrollment: EnrollmentOut];
}>();

const message = useMessage();
const step = ref(0);
const uploading = ref(false);
const uploaded = ref(false);
const clipFile = ref<File | null>(null);
const clipperRef = ref<InstanceType<typeof VideoClipper> | null>(null);

const steps = [
  { title: "Intro", description: "How video clips work" },
  { title: "Trim", description: "Select a short segment" },
  { title: "Upload", description: "Add to enrollment" },
  { title: "Done", description: "Clip saved" },
];

const showModality = computed(() => props.enrollmentType === "person");

watch(show, (open) => {
  if (!open) {
    step.value = 0;
    clipFile.value = null;
    uploading.value = false;
    uploaded.value = false;
  }
});

async function uploadClip() {
  if (!clipFile.value) {
    message.warning("Extract a clip first");
    return;
  }
  uploading.value = true;
  try {
    const modality = (clipperRef.value?.modality ?? "both") as VideoModalityChoice;
    const meta = [
      {
        source: "video_clipper",
        original_filename: clipFile.value.name,
        content_type: clipFile.value.type,
        size_bytes: clipFile.value.size,
        video_modalities: JSON.parse(videoModalitiesParam(modality)),
      },
    ];
    const form = new FormData();
    form.append("sample_meta", JSON.stringify(meta));
    form.append("video_modalities", videoModalitiesParam(modality));
    form.append("files", clipFile.value);
    const updated = await apiForm<EnrollmentOut>(
      `/v1/enrollments/${props.enrollmentId}/samples`,
      form,
    );
    emit("completed", updated);
    uploaded.value = true;
    step.value = 3;
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Upload failed");
  } finally {
    uploading.value = false;
  }
}
</script>

<template>
  <GuidedCaptureModal
    v-model:show="show"
    :title="`Video clip — ${enrollmentLabel}`"
    :steps="steps"
    :current="step"
    layout="progress"
  >
    <div v-if="step === 0" class="step-body">
      <p>
        Load a longer video from your device, then trim a short segment where
        <strong>{{ enrollmentLabel }}</strong>
        is clearly visible or speaking.
      </p>
      <ul class="step-list">
        <li>Only the trimmed clip is uploaded — not the full file.</li>
        <li>
          Recommended length: {{ DEFAULT_VIDEO_LIMITS.recommended_sec[0] }}–{{
            DEFAULT_VIDEO_LIMITS.recommended_sec[1]
          }}
          seconds (max {{ DEFAULT_VIDEO_LIMITS.enrollment_max_sec }}s).
        </li>
        <li v-if="enrollmentType === 'person'">
          Choose whether to extract face frames, voice, or both from the clip.
        </li>
        <li v-else-if="enrollmentType === 'sound'">
          Audio from the clip is used for sound-event enrollment.
        </li>
        <li v-else>Frames from the clip are used for visual matching.</li>
      </ul>
    </div>

    <div v-else-if="step === 1" class="step-body">
      <VideoClipper
        ref="clipperRef"
        v-model="clipFile"
        mode="enrollment"
        :enrollment-type="enrollmentType"
        :show-modality-choice="showModality"
      />
    </div>

    <div v-else-if="step === 2" class="step-body">
      <p v-if="clipFile">
        Ready to add <strong>{{ clipFile.name }}</strong> to {{ enrollmentLabel }}'s training
        data.
      </p>
      <p v-else class="muted">Go back and extract a clip first.</p>
    </div>

    <div v-else class="step-body">
      <NAlert type="success" title="Video clip saved">
        Added to <strong>{{ enrollmentLabel }}</strong>. Run Evaluate on the profile to update
        quality, then test recognition.
      </NAlert>
    </div>

    <template #footer>
      <NSpace justify="space-between" style="width: 100%">
        <NButton quaternary @click="show = false">{{ uploaded ? "Close" : "Cancel" }}</NButton>
        <NSpace>
          <NButton v-if="step > 0 && step < 3" :disabled="uploading" @click="step -= 1">Back</NButton>
          <NButton v-if="step < 2" type="primary" :disabled="step === 1 && !clipFile" @click="step += 1">
            {{ step === 0 ? "Start trimming" : "Review" }}
          </NButton>
          <NButton
            v-else-if="step === 2"
            type="primary"
            :loading="uploading"
            :disabled="!clipFile"
            @click="uploadClip"
          >
            Add clip to enrollment
          </NButton>
          <NButton v-else type="primary" @click="show = false">Done</NButton>
        </NSpace>
      </NSpace>
    </template>
  </GuidedCaptureModal>
</template>

<style scoped>
.step-body {
  font-size: 0.9rem;
  line-height: 1.5;
  color: var(--n-text-color-2);
}

.step-list {
  margin: 12px 0 0;
  padding-left: 1.2rem;
}

.muted {
  color: var(--n-text-color-3);
}
</style>
