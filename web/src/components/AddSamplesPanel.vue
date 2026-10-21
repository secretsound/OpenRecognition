<script setup lang="ts">
import { computed, ref } from "vue";
import {
  NCard,
  NButton,
  NButtonGroup,
  NUpload,
  NUploadDragger,
  NTag,
  NSpace,
  NIcon,
  NDivider,
  useMessage,
} from "naive-ui";
import type { UploadFileInfo } from "naive-ui";
import {
  MicOutline,
  CloudUploadOutline,
  CameraOutline,
  MusicalNotesOutline,
  ImagesOutline,
  FolderOpenOutline,
  VideocamOutline,
} from "@vicons/ionicons5";
import CameraCapture from "@/components/CameraCapture.vue";
import type { EnrollmentType, QualityInfo } from "@/types/api";
import {
  mediaConfigFor,
  modalitySampleCount,
  sampleMethodsFor,
} from "@/utils/enrollmentMedia";

const fileList = defineModel<UploadFileInfo[]>("fileList", { required: true });

const props = defineProps<{
  enrollmentType: EnrollmentType;
  uploading?: boolean;
  quality?: QualityInfo | null;
}>();

const emit = defineEmits<{
  upload: [];
  "open-voice-wizard": [];
  "open-face-wizard": [];
  "open-photo-wizard": [];
  "open-video-wizard": [];
}>();

const supportsVideoWizard = computed(
  () =>
    props.enrollmentType === "person" ||
    props.enrollmentType === "pet" ||
    props.enrollmentType === "object" ||
    props.enrollmentType === "sound",
);

const supportsPhotoWizard = computed(
  () => props.enrollmentType === "pet" || props.enrollmentType === "object",
);

const message = useMessage();
const uploadMode = ref<"files" | "camera">("files");
const cameraRef = ref<InstanceType<typeof CameraCapture> | null>(null);

const mediaConfig = computed(() => mediaConfigFor(props.enrollmentType));
const methods = computed(() => sampleMethodsFor(props.enrollmentType));

const supportsVoiceWizard = computed(
  () => props.enrollmentType === "person" || props.enrollmentType === "sound",
);

const showSplitLayout = computed(() => props.enrollmentType === "person");

const supportsCamera = computed(
  () =>
    props.enrollmentType === "person" ||
    props.enrollmentType === "pet" ||
    props.enrollmentType === "object",
);

const pendingCount = computed(() => fileList.value.length);

const voiceSampleCount = computed(() =>
  modalitySampleCount(props.quality?.modalities, "audio"),
);

const faceSampleCount = computed(() =>
  modalitySampleCount(props.quality?.modalities, "image"),
);

const voiceStatusTag = computed(() => {
  const n = voiceSampleCount.value;
  if (n === null) return null;
  if (n === 0) return { type: "warning" as const, label: "No voice samples" };
  return { type: "success" as const, label: `${n} voice sample${n === 1 ? "" : "s"}` };
});

const faceStatusTag = computed(() => {
  const n = faceSampleCount.value;
  if (n === null) return null;
  if (n === 0) return { type: "default" as const, label: "No face photos yet" };
  return { type: "success" as const, label: `${n} face sample${n === 1 ? "" : "s"}` };
});

function clearFiles() {
  fileList.value = [];
  cameraRef.value?.stopCamera();
}

function onCameraCapture(file: File) {
  const id = `camera-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  fileList.value = [
    ...fileList.value,
    {
      id,
      name: file.name,
      status: "finished",
      file,
    },
  ];
  message.success("Photo added — capture more or upload when ready");
}

const cameraHint = computed(() => {
  if (props.enrollmentType === "person") {
    return "Capture face photos from different angles. Each capture is added to your upload queue.";
  }
  if (props.enrollmentType === "pet") {
    return "Capture clear whole-body or face shots. Add several before uploading.";
  }
  return "Capture the object from a few angles, then upload all at once.";
});
</script>

<template>
  <NCard class="samples-card" :bordered="false">
    <template #header>
      <div class="card-header">
        <div>
          <h2 class="card-title">How to add samples</h2>
          <p class="card-subtitle">{{ mediaConfig.hint }}</p>
        </div>
        <NTag v-if="pendingCount > 0" round :bordered="false" type="info">
          {{ pendingCount }} file{{ pendingCount === 1 ? "" : "s" }} selected
        </NTag>
      </div>
    </template>

    <div class="samples-grid" :class="{ 'samples-grid--split': showSplitLayout }">
      <!-- Voice / guided path -->
      <section
        v-if="supportsVoiceWizard"
        class="method-panel method-panel--voice"
      >
        <div class="method-icon-wrap method-icon-wrap--voice">
          <NIcon size="28" :component="enrollmentType === 'sound' ? MusicalNotesOutline : MicOutline" />
        </div>
        <div class="method-body">
          <div class="method-head">
            <h3 class="method-title">
              {{ enrollmentType === "sound" ? "Record a sound" : "Record a voice" }}
            </h3>
            <NTag
              v-if="voiceStatusTag"
              size="small"
              :type="voiceStatusTag.type"
              :bordered="false"
            >
              {{ voiceStatusTag.label }}
            </NTag>
          </div>
          <p class="method-desc">
            {{
              enrollmentType === "sound"
                ? "Record a few clips of this sound with the step-by-step wizard."
                : "Read short phrases so the server learns how you sound. A quiet room works best."
            }}
          </p>
          <NSpace vertical :size="8">
            <NButton type="primary" class="method-cta" @click="emit('open-voice-wizard')">
              <template #icon>
                <NIcon><MicOutline /></NIcon>
              </template>
              Start guided voice
            </NButton>
            <NButton
              v-if="enrollmentType === 'person'"
              secondary
              class="method-cta"
              @click="emit('open-face-wizard')"
            >
              Guided face angles
            </NButton>
            <NButton
              v-if="supportsVideoWizard"
              secondary
              class="method-cta"
              @click="emit('open-video-wizard')"
            >
              <template #icon>
                <NIcon><VideocamOutline /></NIcon>
              </template>
              Trim video clip
            </NButton>
          </NSpace>
        </div>
      </section>

      <section
        v-else-if="supportsPhotoWizard"
        class="method-panel method-panel--voice"
      >
        <div class="method-icon-wrap method-icon-wrap--voice">
          <NIcon size="28"><ImagesOutline /></NIcon>
        </div>
        <div class="method-body">
          <h3 class="method-title">Guided photos</h3>
          <p class="method-desc">{{ mediaConfig.detail }}</p>
          <NButton type="primary" class="method-cta" @click="emit('open-photo-wizard')">
            Start guided photo capture
          </NButton>
          <NButton
            v-if="supportsVideoWizard"
            secondary
            class="method-cta"
            style="margin-top: 8px"
            @click="emit('open-video-wizard')"
          >
            Trim video clip
          </NButton>
        </div>
      </section>

      <NDivider
        v-if="showSplitLayout"
        vertical
        class="samples-divider"
      />

      <!-- File upload path -->
      <section
        class="method-panel method-panel--upload"
        :class="{ 'method-panel--full': !showSplitLayout }"
      >
        <div class="method-icon-wrap method-icon-wrap--upload">
          <NIcon
            size="28"
            :component="
              enrollmentType === 'pet' || enrollmentType === 'object'
                ? ImagesOutline
                : enrollmentType === 'sound'
                  ? MusicalNotesOutline
                  : CameraOutline
            "
          />
        </div>
        <div class="method-body method-body--grow">
          <div class="method-head">
            <h3 class="method-title">
              {{
                enrollmentType === "person"
                  ? "Upload files"
                  : methods[0]?.title ?? "Upload"
              }}
            </h3>
            <NTag
              v-if="enrollmentType === 'person' && faceStatusTag"
              size="small"
              :type="faceStatusTag.type"
              :bordered="false"
            >
              {{ faceStatusTag.label }}
            </NTag>
          </div>
          <p class="method-desc">
            {{
              enrollmentType === "person"
                ? "Drop face photos, voice clips, or both — we detect the type automatically."
                : mediaConfig.detail
            }}
          </p>

          <NButtonGroup v-if="supportsCamera" class="upload-mode-toggle">
            <NButton
              :secondary="uploadMode === 'files'"
              :quaternary="uploadMode !== 'files'"
              size="small"
              @click="uploadMode = 'files'"
            >
              <template #icon>
                <NIcon><FolderOpenOutline /></NIcon>
              </template>
              Browse files
            </NButton>
            <NButton
              :secondary="uploadMode === 'camera'"
              :quaternary="uploadMode !== 'camera'"
              size="small"
              @click="uploadMode = 'camera'"
            >
              <template #icon>
                <NIcon><CameraOutline /></NIcon>
              </template>
              Use camera
            </NButton>
          </NButtonGroup>

          <div v-if="!supportsCamera || uploadMode === 'files'" class="upload-zone">
            <NUpload
              v-model:file-list="fileList"
              multiple
              directory-dnd
              :accept="mediaConfig.accept"
              :default-upload="false"
              :show-file-list="true"
              class="samples-upload"
            >
              <NUploadDragger>
                <div class="dragger-inner">
                  <div class="dragger-icon">
                    <NIcon size="40" :depth="3">
                      <CloudUploadOutline />
                    </NIcon>
                  </div>
                  <p class="dragger-title">Drag files here or click to browse</p>
                  <p class="dragger-hint">Multiple files supported</p>
                  <NSpace :size="6" justify="center" class="format-tags dragger-tags">
                    <NTag
                      v-for="tag in mediaConfig.formatTags"
                      :key="tag"
                      size="tiny"
                      :bordered="false"
                    >
                      {{ tag }}
                    </NTag>
                  </NSpace>
                </div>
              </NUploadDragger>
            </NUpload>
          </div>

          <div v-else class="camera-zone">
            <CameraCapture
              ref="cameraRef"
              compact
              :max-height="220"
              capture-label="Add photo"
              :hint="cameraHint"
              facing-mode="user"
              @capture="onCameraCapture"
            />
            <NUpload
              v-if="pendingCount > 0"
              v-model:file-list="fileList"
              multiple
              :show-trigger="false"
              :default-upload="false"
              class="samples-upload samples-upload--hidden-trigger camera-queue"
            />
          </div>

          <div v-if="pendingCount > 0" class="upload-actions">
            <NButton quaternary size="small" :disabled="uploading" @click="clearFiles">
              Clear all
            </NButton>
            <NButton type="primary" :loading="uploading" @click="emit('upload')">
              Upload {{ pendingCount }} file{{ pendingCount === 1 ? "" : "s" }}
            </NButton>
          </div>
        </div>
      </section>
    </div>
  </NCard>
</template>

<style scoped>
.samples-card :deep(.n-card-header) {
  padding-bottom: 8px;
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
}

.card-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.card-subtitle {
  margin: 4px 0 0;
  font-size: 0.85rem;
  color: var(--n-text-color-3);
  line-height: 1.4;
  max-width: 520px;
}

.samples-grid {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.samples-grid--split {
  flex-direction: column;
  gap: var(--or-section-gap);
}

.samples-divider {
  display: none;
}

.method-panel {
  display: flex;
  gap: 16px;
  padding: 20px;
  border-radius: 10px;
  background: var(--n-color-modal);
  border: 1px solid var(--n-border-color);
  flex: 1;
  min-width: 0;
}

.method-panel--full {
  width: 100%;
}

.method-icon-wrap {
  flex-shrink: 0;
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}

.method-icon-wrap--voice {
  color: var(--n-primary-color);
  background: color-mix(in srgb, var(--n-primary-color) 14%, transparent);
}

.method-icon-wrap--upload {
  color: var(--n-text-color-2);
  background: var(--n-action-color);
}

.method-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.method-body--grow {
  flex: 1;
}

.method-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.method-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
}

.method-desc {
  margin: 6px 0 10px;
  font-size: 0.82rem;
  color: var(--n-text-color-3);
  line-height: 1.5;
}

.upload-mode-toggle {
  margin-bottom: 12px;
}

.upload-zone,
.camera-zone {
  margin-top: 4px;
}

.camera-zone {
  padding: 14px;
  border-radius: 8px;
  background: var(--n-color);
  border: 1px solid var(--n-border-color);
}

.samples-upload--hidden-trigger :deep(.n-upload-trigger) {
  display: none;
}

.camera-queue {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--n-border-color);
}

.format-tags {
  margin-bottom: 14px;
}

.method-cta {
  align-self: flex-start;
  margin-top: auto;
}

.samples-upload {
  width: 100%;
}

.samples-upload :deep(.n-upload-trigger) {
  width: 100%;
}

.dragger-inner {
  padding: 28px 20px;
  text-align: center;
}

.dragger-icon {
  margin-bottom: 8px;
  color: var(--n-text-color-3);
}

.dragger-title {
  margin: 0 0 4px;
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--n-text-color-1);
}

.dragger-hint {
  margin: 0 0 12px;
  font-size: 0.8rem;
  color: var(--n-text-color-3);
}

.dragger-tags {
  flex-wrap: wrap;
}

.upload-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--n-border-color);
}

@media (max-width: 900px) {
  .samples-grid--split {
    flex-direction: column;
  }

  .samples-divider {
    display: none;
  }

  .method-panel {
    margin-bottom: 0;
  }

  .samples-grid--split .method-panel + .method-panel {
    margin-top: 12px;
  }
}
</style>
