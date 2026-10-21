<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import {
  NAlert,
  NButton,
  NRadioGroup,
  NRadioButton,
  NSpace,
  NSpin,
  NTag,
  NUpload,
  NUploadDragger,
  useMessage,
} from "naive-ui";
import type { UploadFileInfo } from "naive-ui";
import { CloudUploadOutline, VideocamOutline, PlayOutline, PauseOutline } from "@vicons/ionicons5";
import { NIcon } from "naive-ui";
import type { EnrollmentType } from "@/types/api";
import {
  DEFAULT_VIDEO_LIMITS,
  VIDEO_CODEC_UNSUPPORTED,
  type VideoLimits,
  type VideoModalityChoice,
  clipFileFromBlob,
  drawVideoFrame,
  extractVideoClip,
  formatDuration,
  loadVideoMetadata,
  validateClipDuration,
  validateClipSize,
} from "@/utils/videoClip";

const props = withDefaults(
  defineProps<{
    mode: "enrollment" | "test";
    enrollmentType?: EnrollmentType;
    limits?: VideoLimits;
    showModalityChoice?: boolean;
  }>(),
  {
    limits: () => DEFAULT_VIDEO_LIMITS,
    showModalityChoice: true,
  },
);

const model = defineModel<File | null>({ default: null });

const message = useMessage();

const sourceFile = ref<File | null>(null);
const previewUrl = ref<string | null>(null);
const durationSec = ref(0);
const startSec = ref(0);
const endSec = ref(30);
const extracting = ref(false);
const modality = ref<VideoModalityChoice>("both");
const loadError = ref<string | null>(null);
const videoDecodeWarning = ref<string | null>(null);
const hasVideoTrack = ref(true);

const videoRef = ref<HTMLVideoElement | null>(null);
const canvasRef = ref<HTMLCanvasElement | null>(null);
const trackRef = ref<HTMLElement | null>(null);
const playheadSec = ref(0);
const dragging = ref<"start" | "end" | null>(null);
const isPlaying = ref(false);
const isSeeking = ref(false);
let seekToken = 0;

const MIN_GAP_SEC = 0.5;

const maxDurationSec = computed(() =>
  props.mode === "enrollment"
    ? props.limits.enrollment_max_sec
    : props.limits.recognize_sync_max_sec,
);

const recommended = computed(() => props.limits.recommended_sec);

const clipDurationSec = computed(() => Math.max(0, endSec.value - startSec.value));

const durationError = computed(() =>
  validateClipDuration(clipDurationSec.value, maxDurationSec.value),
);

const startPct = computed(() =>
  durationSec.value > 0 ? (startSec.value / durationSec.value) * 100 : 0,
);
const endPct = computed(() =>
  durationSec.value > 0 ? (endSec.value / durationSec.value) * 100 : 100,
);
const playheadPct = computed(() =>
  durationSec.value > 0 ? (playheadSec.value / durationSec.value) * 100 : 0,
);
const selectionWidthPct = computed(() => Math.max(0, endPct.value - startPct.value));

const showModality = computed(() => {
  if (!props.showModalityChoice) return false;
  if (props.mode === "test") return true;
  return props.enrollmentType === "person";
});

const modalityHint = computed(() => {
  if (props.enrollmentType === "person") {
    return "Both extracts face frames and speech from the trimmed clip.";
  }
  if (props.enrollmentType === "pet" || props.enrollmentType === "object") {
    return "Video samples are used for visual matching only.";
  }
  return "Choose which pipelines to run on the trimmed clip.";
});

const hintText = computed(() => {
  const rec = `${recommended.value[0]}–${recommended.value[1]}s`;
  const max = formatDuration(maxDurationSec.value);
  if (props.mode === "enrollment") {
    return `Load a video, drag the handles on the timeline to select a ${rec} segment (max ${max}), then extract.`;
  }
  return `Drag the timeline handles to pick your test segment (recommended ${rec}, max ${max}).`;
});

function revokePreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = null;
  }
}

function stopDragListeners() {
  window.removeEventListener("pointermove", onPointerMove);
  window.removeEventListener("pointerup", onPointerUp);
}

function resetAll() {
  stopDragListeners();
  dragging.value = null;
  isPlaying.value = false;
  isSeeking.value = false;
  revokePreview();
  sourceFile.value = null;
  durationSec.value = 0;
  startSec.value = 0;
  endSec.value = 30;
  playheadSec.value = 0;
  loadError.value = null;
  videoDecodeWarning.value = null;
  hasVideoTrack.value = true;
  model.value = null;
}

onBeforeUnmount(resetAll);

watch(
  () => props.enrollmentType,
  (t) => {
    if (t === "sound") modality.value = "audio";
    else if (t === "pet" || t === "object") modality.value = "face";
  },
  { immediate: true },
);

async function onPick(options: { file: UploadFileInfo }) {
  const file = options.file.file;
  if (!file) return;
  loadError.value = null;
  resetAll();
  try {
    const meta = await loadVideoMetadata(file);
    if (meta.durationSec <= 0) {
      throw new Error("Video has no readable duration.");
    }
    sourceFile.value = file;
    durationSec.value = meta.durationSec;
    hasVideoTrack.value = meta.hasVideoTrack;
    if (!meta.hasVideoTrack) {
      videoDecodeWarning.value = VIDEO_CODEC_UNSUPPORTED;
    }
    startSec.value = 0;
    const defaultEnd = Math.min(
      meta.durationSec,
      Math.max(recommended.value[1], 15),
      maxDurationSec.value,
    );
    endSec.value = defaultEnd;
    previewUrl.value = URL.createObjectURL(file);
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : "Could not load video.";
    message.error(loadError.value);
  }
}

function clampSelection(nextStart: number, nextEnd: number, handle: "start" | "end") {
  let s = Math.max(0, Math.min(nextStart, durationSec.value));
  let e = Math.max(0, Math.min(nextEnd, durationSec.value));

  if (e - s < MIN_GAP_SEC) {
    if (handle === "start") s = Math.max(0, e - MIN_GAP_SEC);
    else e = Math.min(durationSec.value, s + MIN_GAP_SEC);
  }

  if (e - s > maxDurationSec.value) {
    if (handle === "start") s = Math.max(0, e - maxDurationSec.value);
    else e = Math.min(durationSec.value, s + maxDurationSec.value);
  }

  startSec.value = s;
  endSec.value = e;
}

function timeFromClientX(clientX: number): number {
  const track = trackRef.value;
  if (!track || durationSec.value <= 0) return 0;
  const rect = track.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
  return ratio * durationSec.value;
}

function onPointerMove(e: PointerEvent) {
  if (!dragging.value) return;
  const t = timeFromClientX(e.clientX);
  if (dragging.value === "start") {
    clampSelection(t, endSec.value, "start");
    seekVideo(startSec.value, { pause: true });
  } else {
    clampSelection(startSec.value, t, "end");
    seekVideo(endSec.value, { pause: true });
  }
}

function onPointerUp(e: PointerEvent) {
  const target = e.target as HTMLElement | null;
  if (target?.releasePointerCapture && target.hasPointerCapture?.(e.pointerId)) {
    try {
      target.releasePointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
  }
  dragging.value = null;
  stopDragListeners();
}

function startDrag(handle: "start" | "end", e: PointerEvent) {
  e.preventDefault();
  dragging.value = handle;
  const el = e.currentTarget as HTMLElement;
  el.setPointerCapture(e.pointerId);
  seekVideo(handle === "start" ? startSec.value : endSec.value, { pause: true });
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", onPointerUp);
}

function seekVideo(sec: number, { pause = false }: { pause?: boolean } = {}) {
  const video = videoRef.value;
  if (!video || durationSec.value <= 0) return;
  const clamped = Math.max(0, Math.min(sec, durationSec.value));
  if (pause || dragging.value) {
    video.pause();
    isPlaying.value = false;
  }
  if (!dragging.value && Math.abs(video.currentTime - clamped) < 0.04) {
    playheadSec.value = clamped;
    paintPreviewFrame();
    return;
  }
  isSeeking.value = true;
  const token = ++seekToken;
  const onSeeked = () => {
    if (token !== seekToken) return;
    video.removeEventListener("seeked", onSeeked);
    isSeeking.value = false;
    playheadSec.value = video.currentTime;
    paintPreviewFrame();
  };
  video.addEventListener("seeked", onSeeked);
  video.currentTime = clamped;
  playheadSec.value = clamped;
}

function togglePlay() {
  const video = videoRef.value;
  if (!video) return;
  if (isPlaying.value) {
    video.pause();
    isPlaying.value = false;
    return;
  }
  if (playheadSec.value >= endSec.value - 0.05) {
    seekVideo(startSec.value, { pause: true });
  } else if (playheadSec.value < startSec.value) {
    seekVideo(startSec.value, { pause: true });
  }
  void video.play().then(() => {
    isPlaying.value = true;
  }).catch(() => {
    isPlaying.value = false;
  });
}

function paintPreviewFrame() {
  const video = videoRef.value;
  const canvas = canvasRef.value;
  if (!video || !canvas) return;
  if (video.videoWidth <= 0) {
    hasVideoTrack.value = false;
    videoDecodeWarning.value = VIDEO_CODEC_UNSUPPORTED;
    return;
  }
  hasVideoTrack.value = true;
  videoDecodeWarning.value = null;
  drawVideoFrame(video, canvas);
}

function onVideoReady() {
  const video = videoRef.value;
  if (!video) return;
  if (video.videoWidth <= 0) {
    hasVideoTrack.value = false;
    videoDecodeWarning.value = VIDEO_CODEC_UNSUPPORTED;
    return;
  }
  seekVideo(startSec.value || 0.01, { pause: true });
}

function onVideoError() {
  videoDecodeWarning.value =
    "Could not decode this video file in the browser. Try H.264 MP4 or VP8/WebM.";
  hasVideoTrack.value = false;
}

function onVideoClick() {
  togglePlay();
}

watch(previewUrl, () => {
  if (previewUrl.value) {
    requestAnimationFrame(() => onVideoReady());
  }
});

function onTrackPointerDown(e: PointerEvent) {
  if ((e.target as HTMLElement).closest(".trim-handle")) return;
  const t = timeFromClientX(e.clientX);
  seekVideo(t, { pause: true });
}

function onTimeUpdate() {
  const video = videoRef.value;
  if (!video || dragging.value) return;
  playheadSec.value = video.currentTime;
  if (isPlaying.value) {
    paintPreviewFrame();
  }
  if (isPlaying.value && video.currentTime >= endSec.value) {
    video.pause();
    isPlaying.value = false;
    seekVideo(endSec.value, { pause: true });
  }
}

function onVideoPause() {
  isPlaying.value = false;
}

function onVideoPlay() {
  isPlaying.value = true;
}

async function extractClip() {
  if (!sourceFile.value) return;
  if (!hasVideoTrack.value) {
    message.warning(videoDecodeWarning.value ?? VIDEO_CODEC_UNSUPPORTED);
    return;
  }
  if (durationError.value) {
    message.warning(durationError.value);
    return;
  }
  extracting.value = true;
  try {
    const blob = await extractVideoClip(sourceFile.value, startSec.value, endSec.value);
    const sizeErr = validateClipSize(blob.size, props.limits.max_upload_bytes);
    if (sizeErr) {
      message.warning(sizeErr);
      return;
    }
    const clip = clipFileFromBlob(blob, sourceFile.value.name);
    model.value = clip;
    message.success(`Clip ready (${formatDuration(clipDurationSec.value)})`);
  } catch (e) {
    message.error(e instanceof Error ? e.message : "Failed to extract clip");
  } finally {
    extracting.value = false;
  }
}

defineExpose({
  modality,
  clipDurationSec,
  startSec,
  endSec,
});
</script>

<template>
  <div class="video-clipper">
    <p class="clipper-hint">{{ hintText }}</p>

    <NUpload
      v-if="!sourceFile"
      :max="1"
      accept="video/*,.mp4,.webm,.mov,.mkv"
      :default-upload="false"
      :show-file-list="false"
      @change="onPick"
    >
      <NUploadDragger>
        <div class="dragger-inner">
          <NIcon size="40" :depth="3"><CloudUploadOutline /></NIcon>
          <p class="dragger-title">Choose a video file</p>
          <p class="dragger-sub">MP4, WebM, MOV — long files OK; only the trimmed clip is uploaded</p>
        </div>
      </NUploadDragger>
    </NUpload>

    <NAlert v-if="loadError" type="error" :bordered="false" style="margin-top: 12px">
      {{ loadError }}
    </NAlert>

    <div v-if="sourceFile && previewUrl" class="trim-panel">
      <div class="video-stage">
        <div class="video-frame" @click="onVideoClick">
          <video
            ref="videoRef"
            class="preview-video"
            :src="previewUrl"
            playsinline
            muted
            preload="auto"
            @loadeddata="onVideoReady"
            @error="onVideoError"
            @timeupdate="onTimeUpdate"
            @pause="onVideoPause"
            @play="onVideoPlay"
          />
          <canvas ref="canvasRef" class="preview-canvas" />
          <div v-if="!hasVideoTrack" class="video-no-track">
            <p>Video track not supported in this browser</p>
            <p class="video-no-track-sub">Audio may still work · convert to H.264 MP4 for face/visual</p>
          </div>
        </div>

        <div class="trim-rail" aria-label="Trim timeline">
          <div class="transport-row">
            <button
              type="button"
              class="transport-btn"
              :aria-label="isPlaying ? 'Pause' : 'Play'"
              @click.stop="togglePlay"
            >
              <NIcon size="18">
                <PauseOutline v-if="isPlaying" />
                <PlayOutline v-else />
              </NIcon>
            </button>
            <span class="transport-time">
              {{ formatDuration(playheadSec) }}
              <span class="transport-time-sep">/</span>
              {{ formatDuration(durationSec) }}
            </span>
            <span v-if="isSeeking" class="transport-scrubbing">Scrubbing…</span>
          </div>

          <div
            ref="trackRef"
            class="trim-track"
            @pointerdown="onTrackPointerDown"
          >
            <div class="trim-dim trim-dim--left" :style="{ width: `${startPct}%` }" />
            <div
              class="trim-selection"
              :style="{ left: `${startPct}%`, width: `${selectionWidthPct}%` }"
            >
              <button
                type="button"
                class="trim-handle trim-handle--start"
                aria-label="Drag start time"
                @pointerdown.stop="startDrag('start', $event)"
              >
                <span class="trim-handle-grip" />
                <span class="trim-handle-time">{{ formatDuration(startSec) }}</span>
              </button>
              <button
                type="button"
                class="trim-handle trim-handle--end"
                aria-label="Drag end time"
                @pointerdown.stop="startDrag('end', $event)"
              >
                <span class="trim-handle-grip" />
                <span class="trim-handle-time">{{ formatDuration(endSec) }}</span>
              </button>
            </div>
            <div class="trim-dim trim-dim--right" :style="{ width: `${100 - endPct}%` }" />
            <div
              class="trim-playhead"
              :style="{ left: `${playheadPct}%` }"
              aria-hidden="true"
            />
          </div>
          <div class="trim-rail-meta">
            <span>0:00</span>
            <span class="trim-rail-selection">
              {{ formatDuration(clipDurationSec) }} selected
            </span>
            <span>{{ formatDuration(durationSec) }}</span>
          </div>
        </div>
      </div>

      <div class="trim-summary">
        <NTag :type="durationError ? 'warning' : 'info'" size="small" :bordered="false">
          {{ formatDuration(startSec) }} → {{ formatDuration(endSec) }}
          ({{ formatDuration(clipDurationSec) }})
        </NTag>
        <NTag size="small" :bordered="false">
          Recommended {{ recommended[0] }}–{{ recommended[1] }}s
        </NTag>
      </div>

      <NAlert v-if="videoDecodeWarning" type="warning" :bordered="false">
        {{ videoDecodeWarning }}
      </NAlert>

      <NAlert v-if="durationError" type="warning" :bordered="false">
        {{ durationError }}
      </NAlert>

      <div v-if="showModality" class="modality-row">
        <span class="trim-label">Use for</span>
        <NRadioGroup v-model:value="modality" size="small">
          <NRadioButton value="both">Both</NRadioButton>
          <NRadioButton value="face">Face / visual</NRadioButton>
          <NRadioButton value="audio">Voice only</NRadioButton>
        </NRadioGroup>
      </div>
      <p v-if="showModality" class="modality-hint">{{ modalityHint }}</p>

      <NSpace :size="8" style="margin-top: 12px">
        <NButton quaternary size="small" :disabled="extracting" @click="resetAll">
          Choose different file
        </NButton>
        <NButton
          type="primary"
          :loading="extracting"
          :disabled="!!durationError || !hasVideoTrack"
          @click="extractClip"
        >
          <template #icon>
            <NIcon><VideocamOutline /></NIcon>
          </template>
          Extract clip
        </NButton>
      </NSpace>

      <NAlert
        v-if="model"
        type="success"
        :bordered="false"
        style="margin-top: 12px"
        title="Clip ready"
      >
        {{ model.name }} ({{ formatDuration(clipDurationSec) }}) — submit when ready.
      </NAlert>
    </div>

    <NSpin v-if="extracting" size="small" style="margin-top: 8px" />
  </div>
</template>

<style scoped>
.video-clipper {
  width: 100%;
}

.clipper-hint {
  margin: 0 0 14px;
  font-size: 0.85rem;
  color: var(--n-text-color-3);
  line-height: 1.45;
}

.dragger-inner {
  padding: 28px 16px;
  text-align: center;
}

.dragger-title {
  margin: 8px 0 4px;
  font-weight: 500;
}

.dragger-sub {
  margin: 0;
  font-size: 0.8rem;
  color: var(--n-text-color-3);
}

.trim-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.video-stage {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--n-border-color);
  background: #000;
}

.video-frame {
  position: relative;
  width: 100%;
  min-height: 160px;
  max-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background: #000;
}

.preview-video {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.preview-canvas {
  display: block;
  width: 100%;
  max-height: 280px;
  object-fit: contain;
}

.video-no-track {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px;
  text-align: center;
  color: rgba(255, 255, 255, 0.75);
  font-size: 0.85rem;
  pointer-events: none;
}

.video-no-track-sub {
  margin: 6px 0 0;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.45);
}

.trim-rail {
  background: rgba(0, 0, 0, 0.85);
  padding: 8px 12px 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.transport-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  min-height: 28px;
}

.transport-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  cursor: pointer;
}

.transport-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.transport-time {
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
  color: rgba(255, 255, 255, 0.82);
}

.transport-time-sep {
  margin: 0 2px;
  color: rgba(255, 255, 255, 0.35);
}

.transport-scrubbing {
  margin-left: auto;
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.45);
}

.trim-track {
  position: relative;
  height: 36px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.12);
  cursor: pointer;
  touch-action: none;
  user-select: none;
}

.trim-dim {
  position: absolute;
  top: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.55);
  pointer-events: none;
}

.trim-dim--left {
  left: 0;
}

.trim-dim--right {
  right: 0;
}

.trim-selection {
  position: absolute;
  top: 0;
  bottom: 0;
  background: rgba(99, 102, 241, 0.45);
  border-top: 2px solid var(--n-primary-color);
  border-bottom: 2px solid var(--n-primary-color);
  min-width: 8px;
  pointer-events: none;
}

.trim-handle {
  position: absolute;
  top: -2px;
  bottom: -2px;
  width: 14px;
  margin: 0;
  padding: 0;
  border: none;
  background: var(--n-primary-color);
  cursor: ew-resize;
  pointer-events: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 2;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.35);
}

.trim-handle--start {
  left: 0;
  transform: translateX(-50%);
  border-radius: 4px 0 0 4px;
}

.trim-handle--end {
  right: 0;
  transform: translateX(50%);
  border-radius: 0 4px 4px 0;
}

.trim-handle:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}

.trim-handle-grip {
  width: 2px;
  height: 14px;
  border-radius: 1px;
  background: rgba(255, 255, 255, 0.85);
  box-shadow: 2px 0 0 rgba(255, 255, 255, 0.85);
}

.trim-handle-time {
  position: absolute;
  bottom: calc(100% + 4px);
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.65rem;
  font-weight: 600;
  line-height: 1;
  padding: 3px 5px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.82);
  color: #fff;
  white-space: nowrap;
  pointer-events: none;
}

.trim-playhead {
  position: absolute;
  top: 2px;
  bottom: 2px;
  width: 2px;
  margin-left: -1px;
  background: #fff;
  box-shadow: 0 0 4px rgba(255, 255, 255, 0.8);
  pointer-events: none;
  z-index: 1;
}

.trim-rail-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.55);
}

.trim-rail-selection {
  color: rgba(255, 255, 255, 0.82);
  font-weight: 500;
}

.trim-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.trim-label {
  font-size: 0.8rem;
  color: var(--n-text-color-3);
}

.modality-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.modality-hint {
  margin: 0;
  font-size: 0.78rem;
  color: var(--n-text-color-3);
}
</style>
