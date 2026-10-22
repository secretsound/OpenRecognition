<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  NButton,
  NButtonGroup,
  NUpload,
  NUploadDragger,
  NTag,
  NSpace,
  NIcon,
  useMessage,
} from "naive-ui";
import type { UploadFileInfo } from "naive-ui";
import {
  MicOutline,
  CloudUploadOutline,
  CameraOutline,
  FolderOpenOutline,
  VideocamOutline,
  ImagesOutline,
} from "@vicons/ionicons5";
import CameraCapture from "@/components/CameraCapture.vue";
import SegmentedControl from "@/components/kit/SegmentedControl.vue";
import type { EnrollmentType, QualityInfo } from "@/types/api";
import { mediaConfigFor, modalitySampleCount } from "@/utils/enrollmentMedia";

type TeachKind = "voice" | "photo" | "video";

const fileList = defineModel<UploadFileInfo[]>("fileList", { required: true });

const props = withDefaults(
  defineProps<{
    enrollmentType: EnrollmentType;
    uploading?: boolean;
    quality?: QualityInfo | null;
    chrome?: boolean;
  }>(),
  { chrome: true },
);

const emit = defineEmits<{
  upload: [];
  done: [];
  "open-voice-wizard": [];
  "open-face-wizard": [];
  "open-photo-wizard": [];
  "open-video-wizard": [];
}>();

const message = useMessage();
const uploadMode = ref<"files" | "camera">("files");
const cameraRef = ref<InstanceType<typeof CameraCapture> | null>(null);

const kind = ref<TeachKind>(
  props.enrollmentType === "pet" || props.enrollmentType === "object" ? "photo" : "voice",
);

const kindOptions = computed(() => {
  if (props.enrollmentType === "person") {
    return [
      { value: "voice" as const, label: "Voice", hint: "Spoken phrases" },
      { value: "photo" as const, label: "Photo", hint: "Face photos" },
      { value: "video" as const, label: "Video", hint: "A short clip" },
    ];
  }
  if (props.enrollmentType === "sound") {
    return [
      { value: "voice" as const, label: "Sound", hint: "Audio clips" },
      { value: "video" as const, label: "Video", hint: "A short clip" },
    ];
  }
  return [
    { value: "photo" as const, label: "Photo", hint: "Still photos" },
    { value: "video" as const, label: "Video", hint: "A short clip" },
  ];
});

const mediaConfig = computed(() => mediaConfigFor(props.enrollmentType));
const pendingCount = computed(() => fileList.value.length);

const voiceCount = computed(() => modalitySampleCount(props.quality?.modalities, "audio") ?? 0);
const photoCount = computed(() => modalitySampleCount(props.quality?.modalities, "image") ?? 0);

const accept = computed(() => {
  if (kind.value === "voice") return "audio/*,.wav,.mp3,.flac,.ogg,.m4a,.aac,.webm";
  if (kind.value === "photo") return "image/*,.jpg,.jpeg,.png,.webp";
  return "video/*,.mp4,.webm,.mov";
});

const formatTags = computed(() => {
  if (kind.value === "voice") return ["WAV", "MP3", "FLAC", "OGG"];
  if (kind.value === "photo") return ["JPEG", "PNG", "WebP"];
  return ["MP4", "WebM", "MOV"];
});

const copy = computed(() => {
  if (kind.value === "voice" && props.enrollmentType === "sound") {
    return {
      title: "Teach this sound",
      body: "Record a few clear clips of the same event. Variation in timing helps more than one long file.",
      guided: "Start guided capture",
      upload: "Or drop audio files you already have.",
    };
  }
  if (kind.value === "voice") {
    return {
      title: voiceCount.value > 0 ? "Improve this voice" : "Teach this voice",
      body:
        voiceCount.value > 0
          ? "New phrases plus a few ways you actually talk to a speaker — next to you, quieter, or from across the room."
          : "Read short sentences the way you actually talk to a speaker — next to you, or calling from across the room — not just one careful take.",
      guided: voiceCount.value > 0 ? "Record more phrases" : "Start voice training",
      upload: "Or drop voice clips if you already recorded them.",
    };
  }
  if (kind.value === "photo" && props.enrollmentType === "person") {
    return {
      title: "Teach this face",
      body:
        photoCount.value > 0
          ? "Add new angles — from the side, closer, or a few steps back like a doorbell would see you."
          : "A doorbell or room camera rarely sees a passport photo. We'll walk through the views that actually show up.",
      guided: photoCount.value > 0 ? "Add more face photos" : "Start face training",
      upload: "Or add photos from files or the camera.",
    };
  }
  if (kind.value === "photo") {
    return {
      title: props.enrollmentType === "pet" ? "Teach this pet" : "Teach this object",
      body:
        photoCount.value > 0
          ? "New angles and distances help more than another copy of the same shot."
          : mediaConfig.value.detail,
      guided: photoCount.value > 0 ? "Add more photos" : "Start guided photos",
      upload: "Or drop photos you already have.",
    };
  }
  return {
    title: "Teach from video",
    body: "Trim a short clip. The server will pull the useful frames and audio.",
    guided: "Trim a video clip",
    upload: "Or drop a video file to trim next.",
  };
});

function clearFiles() {
  fileList.value = [];
  cameraRef.value?.stopCamera();
}

watch(kind, () => {
  clearFiles();
  uploadMode.value = "files";
});

function startGuided() {
  if (kind.value === "voice") emit("open-voice-wizard");
  else if (kind.value === "video") emit("open-video-wizard");
  else if (props.enrollmentType === "person") emit("open-face-wizard");
  else emit("open-photo-wizard");
}

function onCameraCapture(file: File) {
  const id = `camera-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  fileList.value = [
    ...fileList.value,
    { id, name: file.name, status: "finished", file },
  ];
  message.success("Photo added — capture more or upload when ready");
}
</script>

<template>
  <div class="teach">
    <div v-if="chrome" class="teach__head">
      <div>
        <h2 class="or-heading">Add samples</h2>
        <p class="or-muted or-small" style="margin-top: 4px">
          Pick what to teach, then record or upload. One kind at a time is easier.
        </p>
      </div>
      <div class="teach__head-actions">
        <NTag v-if="pendingCount > 0" round :bordered="false" type="info">
          {{ pendingCount }} file{{ pendingCount === 1 ? "" : "s" }} selected
        </NTag>
        <NButton quaternary @click="emit('done')">Done</NButton>
      </div>
    </div>

    <SegmentedControl
      v-model="kind"
      aria-label="What to teach"
      :options="kindOptions"
    />

    <section class="or-surface or-surface--md teach-pane">
      <div class="teach-pane__intro">
        <div>
          <p class="or-caps">{{ copy.title }}</p>
          <p class="or-muted" style="margin-top: 6px">{{ copy.body }}</p>
        </div>
        <div class="teach-pane__counts">
          <span v-if="kind === 'voice'" class="or-muted or-small">
            {{ voiceCount }} voice sample{{ voiceCount === 1 ? "" : "s" }}
          </span>
          <span v-else-if="kind === 'photo'" class="or-muted or-small">
            {{ photoCount }} photo{{ photoCount === 1 ? "" : "s" }}
          </span>
        </div>
      </div>

      <NButton type="primary" @click="startGuided">
        <template #icon>
          <NIcon>
            <MicOutline v-if="kind === 'voice'" />
            <VideocamOutline v-else-if="kind === 'video'" />
            <ImagesOutline v-else />
          </NIcon>
        </template>
        {{ copy.guided }}
      </NButton>

      <p class="or-muted or-small" style="margin-top: 18px">{{ copy.upload }}</p>

      <NButtonGroup v-if="kind === 'photo'" class="upload-mode-toggle">
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

      <div v-if="kind !== 'photo' || uploadMode === 'files'" class="upload-zone">
        <NUpload
          v-model:file-list="fileList"
          multiple
          directory-dnd
          :accept="accept"
          :default-upload="false"
          :show-file-list="true"
          class="samples-upload"
        >
          <NUploadDragger>
            <div class="dragger-inner">
              <NIcon size="36" :depth="3"><CloudUploadOutline /></NIcon>
              <p class="dragger-title">Drag files here or click to browse</p>
              <NSpace :size="6" justify="center" class="dragger-tags">
                <NTag v-for="tag in formatTags" :key="tag" size="tiny" :bordered="false">
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
          hint="Capture a few angles, then upload them together."
          facing-mode="user"
          @capture="onCameraCapture"
        />
        <NUpload
          v-if="pendingCount > 0"
          v-model:file-list="fileList"
          multiple
          :show-trigger="false"
          :default-upload="false"
          class="samples-upload samples-upload--hidden-trigger"
        />
      </div>

      <div v-if="pendingCount > 0" class="upload-actions">
        <NButton quaternary size="small" :disabled="uploading" @click="clearFiles">
          Clear
        </NButton>
        <NButton type="primary" :loading="uploading" @click="emit('upload')">
          Upload {{ pendingCount }} file{{ pendingCount === 1 ? "" : "s" }}
        </NButton>
      </div>
    </section>
  </div>
</template>

<style scoped>
.teach {
  display: flex;
  flex-direction: column;
  gap: var(--or-space-4);
}

.teach__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.teach__head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.teach-pane {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.teach-pane__intro {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  margin-bottom: 14px;
}

.upload-mode-toggle {
  margin: 10px 0 4px;
}

.upload-zone,
.camera-zone {
  width: 100%;
  margin-top: 10px;
}

.camera-zone {
  padding: 14px;
  border-radius: var(--or-radius-md);
  border: 1px solid var(--or-line);
}

.samples-upload {
  width: 100%;
}

.samples-upload :deep(.n-upload-trigger) {
  width: 100%;
}

.samples-upload--hidden-trigger :deep(.n-upload-trigger) {
  display: none;
}

.dragger-inner {
  padding: 22px 16px;
  text-align: center;
}

.dragger-title {
  margin: 8px 0 8px;
  font-weight: 500;
}

.dragger-tags {
  flex-wrap: wrap;
}

.upload-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  width: 100%;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--or-line);
}
</style>
