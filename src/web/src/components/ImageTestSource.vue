<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  NButton,
  NUpload,
  NUploadDragger,
  NIcon,
  NTag,
  NSpace,
  useMessage,
} from "naive-ui";
import type { UploadFileInfo } from "naive-ui";
import {
  CloudUploadOutline,
  ImageOutline,
  RefreshOutline,
} from "@vicons/ionicons5";
import CameraCapture from "@/components/CameraCapture.vue";

const file = defineModel<File | null>({ required: true });

const message = useMessage();

const source = ref<"upload" | "camera" | null>(null);
const fileList = ref<UploadFileInfo[]>([]);
const previewUrl = ref<string | null>(null);
const imageMeta = ref<{ width: number; height: number; sizeLabel: string } | null>(null);
const cameraRef = ref<InstanceType<typeof CameraCapture> | null>(null);

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function revokePreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = null;
  }
}

async function loadImageMeta(f: File) {
  revokePreview();
  previewUrl.value = URL.createObjectURL(f);
  const dims = await new Promise<{ width: number; height: number }>((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
    img.onerror = () => reject(new Error("Could not read image"));
    img.src = previewUrl.value!;
  });
  imageMeta.value = {
    ...dims,
    sizeLabel: formatSize(f.size),
  };
}

async function setFile(f: File) {
  file.value = f;
  await loadImageMeta(f).catch(() => {
    imageMeta.value = { width: 0, height: 0, sizeLabel: formatSize(f.size) };
  });
}

function syncFileFromUpload() {
  const f = fileList.value.map((x) => x.file).find((x): x is File => x != null);
  if (f) {
    void setFile(f);
  } else {
    file.value = null;
    revokePreview();
    imageMeta.value = null;
  }
}

watch(source, (mode) => {
  fileList.value = [];
  file.value = null;
  revokePreview();
  imageMeta.value = null;
  if (mode === "upload") {
    cameraRef.value?.stopCamera();
  }
});

watch(fileList, syncFileFromUpload, { deep: true });

async function onCameraCapture(captured: File) {
  fileList.value = [];
  await setFile(captured);
  message.success("Photo captured — run the test when ready");
}

function clearImage() {
  fileList.value = [];
  file.value = null;
  revokePreview();
  imageMeta.value = null;
}

const hasImage = computed(() => file.value != null);
</script>

<template>
  <div class="image-source">
    <div v-if="!source" class="source-choices">
      <button type="button" class="or-choice-card" @click="source = 'upload'">
        <span class="or-choice-card__title">Upload a photo</span>
        <span class="or-choice-card__desc">Use a picture you already have.</span>
      </button>
      <button type="button" class="or-choice-card" @click="source = 'camera'">
        <span class="or-choice-card__title">Use the camera</span>
        <span class="or-choice-card__desc">Take a photo now and check it.</span>
      </button>
    </div>

    <NButton v-else text type="primary" class="source-switch" @click="source = source === 'upload' ? 'camera' : 'upload'">
      {{ source === "upload" ? "Use the camera instead" : "Upload a photo instead" }}
    </NButton>

    <div v-if="source === 'upload'" class="source-panel">
      <NUpload
        v-model:file-list="fileList"
        :max="1"
        directory-dnd
        accept="image/*,.jpg,.jpeg,.png,.webp,.gif,.bmp"
        :default-upload="false"
        :show-file-list="false"
        class="upload-area"
        @remove="clearImage"
      >
        <NUploadDragger>
          <div class="dragger-inner">
            <NIcon size="36" :depth="3"><CloudUploadOutline /></NIcon>
            <p class="dragger-title">Drag a photo here or click to browse</p>
            <p class="dragger-hint">JPEG, PNG, WebP — faces, pets, and objects</p>
          </div>
        </NUploadDragger>
      </NUpload>
    </div>

    <div v-else-if="source === 'camera'" class="source-panel source-panel--camera">
      <CameraCapture
        ref="cameraRef"
        hint="Frame your subject, then capture. The preview below updates after capture."
        @capture="onCameraCapture"
      />
    </div>

    <div v-if="hasImage && previewUrl" class="preview-panel">
      <div class="preview-header">
        <NSpace align="center" :size="8">
          <NIcon size="18" color="var(--n-primary-color)"><ImageOutline /></NIcon>
          <span class="preview-title">Ready to test</span>
        </NSpace>
        <NButton quaternary size="small" @click="clearImage">
          <template #icon>
            <NIcon><RefreshOutline /></NIcon>
          </template>
          Clear
        </NButton>
      </div>
      <div class="preview-layout">
        <img :src="previewUrl" alt="Test preview" class="preview-img" />
        <div class="preview-meta">
          <p class="preview-name">{{ file?.name }}</p>
          <p v-if="imageMeta" class="preview-details">
            {{ imageMeta.width }}×{{ imageMeta.height }} · {{ imageMeta.sizeLabel }}
          </p>
          <NTag size="small" type="success" :bordered="false">Image loaded</NTag>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.image-source {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.source-choices {
  display: flex;
  flex-direction: column;
  gap: var(--or-inline-gap);
}

.source-switch {
  align-self: flex-start;
}

.source-panel {
  padding: 20px;
  border-radius: 10px;
  background: var(--n-color-modal);
  border: 1px solid var(--n-border-color);
}

.source-panel--camera {
  padding: 16px 18px;
}

.upload-area {
  width: 100%;
}

.upload-area :deep(.n-upload-trigger) {
  width: 100%;
}

.dragger-inner {
  padding: 24px 16px;
  text-align: center;
}

.dragger-title {
  margin: 10px 0 4px;
  font-size: 0.95rem;
  font-weight: 500;
}

.dragger-hint {
  margin: 0;
  font-size: 0.8rem;
  color: var(--n-text-color-3);
}

.preview-panel {
  padding: 16px 18px;
  border-radius: 10px;
  background: var(--n-color-modal);
  border: 1px solid rgba(24, 160, 88, 0.35);
  box-shadow: 0 0 0 1px rgba(24, 160, 88, 0.08);
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.preview-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--n-primary-color);
}

.preview-layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.preview-img {
  width: 140px;
  height: 140px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid var(--n-border-color);
  background: var(--n-action-color);
}

.preview-meta {
  flex: 1;
  min-width: 160px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-name {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 500;
  word-break: break-all;
}

.preview-details {
  margin: 0;
  font-size: 0.8rem;
  color: var(--n-text-color-3);
}

@media (max-width: 520px) {
  .preview-layout {
    flex-direction: column;
  }

  .preview-img {
    width: 100%;
    max-width: 240px;
    height: auto;
    aspect-ratio: 1;
  }
}
</style>
