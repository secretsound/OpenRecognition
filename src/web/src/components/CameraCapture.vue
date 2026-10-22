<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { NButton, NIcon, NAlert, NTag, useMessage } from "naive-ui";
import { CameraOutline } from "@vicons/ionicons5";
import { isSecureEnoughForMic } from "@/utils/secureContext";

const props = withDefaults(
  defineProps<{
    /** Shown under the viewport while the camera is active. */
    hint?: string;
    captureLabel?: string;
    allowLabel?: string;
    facingMode?: "user" | "environment";
    maxHeight?: number;
    compact?: boolean;
    autostart?: boolean;
    guide?: "face" | "none";
  }>(),
  {
    hint: "Frame your subject, then capture.",
    captureLabel: "Capture photo",
    allowLabel: "Allow camera",
    facingMode: "user",
    maxHeight: 280,
    compact: false,
    autostart: false,
    guide: "none",
  },
);

const emit = defineEmits<{
  capture: [file: File];
}>();

const message = useMessage();
const videoRef = ref<HTMLVideoElement | null>(null);
const cameraReady = ref(false);
const cameraActive = ref(false);
const pendingFile = ref<File | null>(null);
const previewUrl = ref<string | null>(null);
let mediaStream: MediaStream | null = null;

function clearPending() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = null;
  pendingFile.value = null;
}

function stopCamera() {
  mediaStream?.getTracks().forEach((t) => t.stop());
  mediaStream = null;
  cameraActive.value = false;
  cameraReady.value = false;
  clearPending();
  if (videoRef.value) videoRef.value.srcObject = null;
}

async function startCamera() {
  stopCamera();
  if (!navigator.mediaDevices?.getUserMedia) {
    message.error("Camera is not supported in this browser.");
    return;
  }
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: props.facingMode,
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    });
    cameraActive.value = true;
    cameraReady.value = true;
    await new Promise((r) => requestAnimationFrame(r));
    if (videoRef.value) {
      videoRef.value.srcObject = mediaStream;
      await videoRef.value.play();
    }
  } catch (e) {
    message.error(e instanceof Error ? e.message : "Camera permission denied");
    stopCamera();
  }
}

async function capturePhoto() {
  const video = videoRef.value;
  if (!video || !cameraActive.value) return;
  const w = video.videoWidth;
  const h = video.videoHeight;
  if (!w || !h) {
    message.warning("Camera is still starting — try again in a moment");
    return;
  }
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.drawImage(video, 0, 0, w, h);
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob((b) => resolve(b), "image/jpeg", 0.92),
  );
  if (!blob) {
    message.error("Could not capture photo");
    return;
  }
  clearPending();
  const file = new File([blob], `camera-capture-${Date.now()}.jpg`, {
    type: "image/jpeg",
  });
  pendingFile.value = file;
  previewUrl.value = URL.createObjectURL(file);
}

function retake() {
  clearPending();
}

function discardPending() {
  clearPending();
}

function usePhoto() {
  const file = pendingFile.value;
  if (!file) return;
  emit("capture", file);
  clearPending();
}

watch(
  () => props.facingMode,
  (next, prev) => {
    if (next !== prev && cameraActive.value) {
      void startCamera();
    }
  },
);

onMounted(() => {
  if (props.autostart) void startCamera();
});

onBeforeUnmount(() => {
  clearPending();
  stopCamera();
});

defineExpose({ stopCamera, discardPending });
</script>

<template>
  <div class="camera-capture" :class="{ 'camera-capture--compact': compact }">
    <NAlert
      v-if="!isSecureEnoughForMic()"
      type="warning"
      :bordered="false"
      title="HTTPS required for camera"
    >
      Use <strong>https://localhost:5173</strong> in dev, or serve the UI over HTTPS.
    </NAlert>

    <template v-else>
      <div class="camera-toolbar">
        <NButton
          v-if="!cameraActive"
          type="primary"
          :size="compact ? 'small' : 'medium'"
          @click="startCamera"
        >
          <template #icon>
            <NIcon><CameraOutline /></NIcon>
          </template>
          {{ allowLabel }}
        </NButton>
        <NTag v-else size="small" type="success" :bordered="false">Camera ready</NTag>
        <NButton v-if="cameraActive" quaternary :size="compact ? 'small' : 'medium'" @click="stopCamera">
          Stop camera
        </NButton>
      </div>

      <div
        v-show="cameraActive && !previewUrl"
        class="camera-viewport"
        :style="{ maxHeight: `${maxHeight}px` }"
      >
        <video
          ref="videoRef"
          class="camera-video"
          :class="{ 'camera-video--mirror': facingMode === 'user' }"
          :style="{ maxHeight: `${maxHeight}px` }"
          playsinline
          muted
        />
        <div
          v-if="guide === 'face'"
          class="camera-guide camera-guide--face"
          aria-hidden="true"
        />
      </div>

      <div
        v-if="previewUrl"
        class="camera-viewport"
        :style="{ maxHeight: `${maxHeight}px` }"
      >
        <img :src="previewUrl" alt="Captured photo" class="camera-still" :style="{ maxHeight: `${maxHeight}px` }" />
      </div>

      <div v-if="previewUrl" class="camera-actions">
        <NButton :size="compact ? 'medium' : 'large'" @click="retake">Retake</NButton>
        <NButton type="primary" :size="compact ? 'medium' : 'large'" @click="usePhoto">
          Use this photo
        </NButton>
      </div>
      <div v-else-if="cameraReady" class="camera-actions">
        <NButton
          type="primary"
          :size="compact ? 'medium' : 'large'"
          :disabled="!cameraActive"
          @click="capturePhoto"
        >
          <template #icon>
            <NIcon><CameraOutline /></NIcon>
          </template>
          {{ captureLabel }}
        </NButton>
      </div>

      <p v-if="cameraActive && hint" class="camera-hint">{{ hint }}</p>
    </template>
  </div>
</template>

<style scoped>
.camera-capture {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.camera-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.camera-viewport {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  background: #000;
  border: 1px solid var(--n-border-color);
  display: flex;
  justify-content: center;
}

.camera-guide--face {
  position: absolute;
  inset: 10% 18%;
  border: 2px dashed rgba(255, 255, 255, 0.7);
  border-radius: 50%;
  pointer-events: none;
  box-shadow: 0 0 0 999px rgba(0, 0, 0, 0.28);
}

.camera-video {
  display: block;
  width: 100%;
  object-fit: contain;
}

.camera-video--mirror {
  transform: scaleX(-1);
}

.camera-still {
  display: block;
  width: 100%;
  object-fit: contain;
}

.camera-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.camera-hint {
  margin: 0;
  font-size: 0.8rem;
  color: var(--n-text-color-3);
  line-height: 1.45;
}

.camera-capture--compact .camera-hint {
  font-size: 0.75rem;
}
</style>
