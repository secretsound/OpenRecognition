<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NSkeleton, useMessage, useNotification } from "naive-ui";
import type { UploadFileInfo } from "naive-ui";
import { api, apiForm } from "@/api/client";
import type { EnrollmentOut, QualityInfo } from "@/types/api";
import { ApiError } from "@/api/client";
import DetailHeader from "@/components/DetailHeader.vue";
import StatusPill from "@/components/StatusPill.vue";
import TypeTag from "@/components/TypeTag.vue";
import AddSamplesPanel from "@/components/AddSamplesPanel.vue";
import VoiceRegistrationModal from "@/components/VoiceRegistrationModal.vue";
import FaceEnrollmentModal from "@/components/FaceEnrollmentModal.vue";
import PhotoEnrollmentModal from "@/components/PhotoEnrollmentModal.vue";
import VideoEnrollmentModal from "@/components/VideoEnrollmentModal.vue";
import { useBreadcrumbOverride } from "@/composables/useBreadcrumbTail";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const notification = useNotification();

const id = computed(() => route.params.id as string);
const loading = ref(true);
const enrollment = ref<EnrollmentOut | null>(null);
const fileList = ref<UploadFileInfo[]>([]);
const uploading = ref(false);
const evaluating = ref(false);
const showVoiceWizard = ref(false);
const showFaceWizard = ref(false);
const showPhotoWizard = ref(false);
const showVideoWizard = ref(false);

useBreadcrumbOverride(
  computed(() => {
    const e = enrollment.value;
    if (!e) return null;
    return [
      { label: "Library", to: "/enrollments" },
      { label: e.label, to: `/enrollments/${e.id}` },
      { label: "Add samples" },
    ];
  }),
);

async function load() {
  loading.value = true;
  try {
    enrollment.value = await api<EnrollmentOut>(`/v1/enrollments/${id.value}`);
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load");
    router.push("/enrollments");
  } finally {
    loading.value = false;
  }
}

async function addSamples() {
  const files = fileList.value.map((f) => f.file).filter((f): f is File => f != null);
  if (files.length === 0) {
    message.warning("Select files to upload");
    return;
  }
  uploading.value = true;
  try {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    enrollment.value = await apiForm<EnrollmentOut>(
      `/v1/enrollments/${id.value}/samples`,
      form,
    );
    fileList.value = [];
    notification.success({
      title: "Samples added",
      content: `${enrollment.value.sample_count} total samples.`,
    });
    router.push({ name: "enrollment-detail", params: { id: enrollment.value.id } });
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Upload failed");
  } finally {
    uploading.value = false;
  }
}

async function evaluate() {
  evaluating.value = true;
  try {
    const q = await api<QualityInfo>(`/v1/enrollments/${id.value}/evaluate`, {
      method: "POST",
    });
    if (enrollment.value) enrollment.value = { ...enrollment.value, quality: q };
    message.success("Quality evaluated");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Evaluate failed");
  } finally {
    evaluating.value = false;
  }
}

function notifySamples(title: string, updated: EnrollmentOut) {
  enrollment.value = updated;
  notification.success({
    title,
    content: `${updated.sample_count} total samples. Check quality when you are ready.`,
  });
  router.push({ name: "enrollment-detail", params: { id: updated.id } });
}

onMounted(load);
</script>

<template>
  <div class="training-page">
    <NSkeleton v-if="loading" text :repeat="6" />

    <template v-else-if="enrollment">
      <DetailHeader
        title="Add samples"
        :description="`Guided capture is the easiest way to teach the server about ${enrollment.label}. You can also upload files you already have.`"
      >
        <template #meta>
          <TypeTag :type="enrollment.type" />
          <StatusPill :enrollment="enrollment" />
          <span class="training-count">{{ enrollment.sample_count }} samples</span>
        </template>
        <template #action>
          <NButton
            :loading="evaluating"
            :disabled="enrollment.sample_count === 0"
            @click="evaluate"
          >
            Check quality
          </NButton>
        </template>
      </DetailHeader>

      <AddSamplesPanel
        v-model:file-list="fileList"
        :enrollment-type="enrollment.type"
        :quality="enrollment.quality"
        :uploading="uploading"
        @upload="addSamples"
        @open-voice-wizard="showVoiceWizard = true"
        @open-face-wizard="showFaceWizard = true"
        @open-photo-wizard="showPhotoWizard = true"
        @open-video-wizard="showVideoWizard = true"
      />

      <VoiceRegistrationModal
        v-model:show="showVoiceWizard"
        :enrollment-id="enrollment.id"
        :enrollment-label="enrollment.label"
        :enrollment-type="enrollment.type"
        @completed="notifySamples('Voice samples added', $event)"
      />

      <FaceEnrollmentModal
        v-if="enrollment.type === 'person'"
        v-model:show="showFaceWizard"
        :enrollment-id="enrollment.id"
        :enrollment-label="enrollment.label"
        @completed="notifySamples('Face photos added', $event)"
      />

      <PhotoEnrollmentModal
        v-if="enrollment.type === 'pet' || enrollment.type === 'object'"
        v-model:show="showPhotoWizard"
        :enrollment-id="enrollment.id"
        :enrollment-label="enrollment.label"
        :enrollment-type="enrollment.type"
        @completed="notifySamples('Photos added', $event)"
      />

      <VideoEnrollmentModal
        v-model:show="showVideoWizard"
        :enrollment-id="enrollment.id"
        :enrollment-label="enrollment.label"
        :enrollment-type="enrollment.type"
        @completed="notifySamples('Video clip added', $event)"
      />
    </template>
  </div>
</template>

<style scoped>
.training-page {
  display: flex;
  flex-direction: column;
  gap: var(--or-section-gap);
}

.training-count {
  color: var(--n-text-color-3);
  font-size: 0.8125rem;
}
</style>
