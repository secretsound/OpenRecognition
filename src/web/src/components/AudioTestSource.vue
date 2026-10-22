<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  NButton,
  NUpload,
  NUploadDragger,
  NIcon,
  NAlert,
  NSelect,
  NTag,
  useMessage,
} from "naive-ui";
import type { UploadFileInfo, SelectOption } from "naive-ui";
import {
  CloudUploadOutline,
  MicOutline,
  StopOutline,
  PlayOutline,
} from "@vicons/ionicons5";
import { useVoiceRecorder } from "@/composables/useVoiceRecorder";
import VoiceWaveform from "@/components/VoiceWaveform.vue";
import { isSecureEnoughForMic } from "@/utils/secureContext";
import { useLiveListen } from "@/composables/useLiveListen";

const file = defineModel<File | null>({ required: true });
const emit = defineEmits<{
  window: [file: File];
  listening: [active: boolean];
}>();

const message = useMessage();
const recorder = useVoiceRecorder();

const waveformSource = {
  levels: recorder.levels,
  level: recorder.audioLevel,
};

const source = ref<"upload" | "record" | "listen" | null>(null);
const live = useLiveListen();
const fileList = ref<UploadFileInfo[]>([]);
const micReady = ref(false);
const micDevices = ref<MediaDeviceInfo[]>([]);
const selectedMicId = ref<string | null>(null);

const minRecordMs = 800;

const micOptions = computed<SelectOption[]>(() =>
  micDevices.value.map((d) => ({
    label: d.label || `Microphone (${d.deviceId.slice(0, 8)}…)`,
    value: d.deviceId,
  })),
);

const recordState = computed(() => recorder.state.value);
const isRecording = computed(() => recordState.value === "recording");
const hasRecording = computed(() => recordState.value === "recorded" && recorder.wavBlob.value != null);

const durationLabel = computed(() => {
  const ms = recorder.durationMs.value;
  const s = Math.floor(ms / 1000);
  const tenths = Math.floor((ms % 1000) / 100);
  return `${s}.${tenths}s`;
});

function syncFileFromUpload() {
  const f = fileList.value.map((x) => x.file).find((x): x is File => x != null);
  file.value = f ?? null;
}

function syncFileFromRecording() {
  const blob = recorder.wavBlob.value;
  if (source.value === "record" && recordState.value === "recorded" && blob) {
    file.value = new File([blob], "test-recording.wav", { type: "audio/wav" });
  } else if (source.value === "record") {
    file.value = null;
  }
}

watch(source, (mode) => {
  fileList.value = [];
  file.value = null;
  recorder.reset();
  live.stop();
  emit("listening", false);
  micReady.value = false;
  if ((mode === "record" || mode === "listen") && isSecureEnoughForMic()) {
    void prepareMic();
  }
});

watch(
  () => live.listening.value,
  (active) => emit("listening", active),
);

watch(fileList, syncFileFromUpload, { deep: true });

watch([recordState, () => recorder.wavBlob.value], syncFileFromRecording);

async function refreshMicDevices() {
  const devices = await navigator.mediaDevices.enumerateDevices();
  micDevices.value = devices.filter((d) => d.kind === "audioinput");
}

async function prepareMic() {
  try {
    await recorder.ensureMic(selectedMicId.value ?? undefined, { meter: false });
    await refreshMicDevices();
    const track = recorder.micStream.value?.getAudioTracks()[0];
    const currentId = track?.getSettings().deviceId;
    if (currentId) selectedMicId.value = currentId;
    micReady.value = true;
  } catch (e) {
    message.error(e instanceof Error ? e.message : "Microphone permission denied");
  }
}

async function changeMicDevice(deviceId: string) {
  try {
    await recorder.ensureMic(deviceId, { meter: false });
    selectedMicId.value = deviceId;
    micReady.value = true;
  } catch (e) {
    message.error(e instanceof Error ? e.message : "Could not open microphone");
  }
}

async function toggleRecord() {
  if (isRecording.value) {
    if (recorder.durationMs.value < minRecordMs) {
      message.warning("Speak a little longer (at least 0.8 seconds)");
      return;
    }
    recorder.stop();
    return;
  }
  if (hasRecording.value) {
    recorder.discardTake();
    file.value = null;
  }
  try {
    if (!micReady.value) await prepareMic();
    await recorder.start();
  } catch (e) {
    message.error(e instanceof Error ? e.message : "Could not start recording");
  }
}

function playPreview() {
  const url = recorder.previewUrl.value;
  if (!url) return;
  const audio = new Audio(url);
  void audio.play();
}

const isListening = computed(() => live.listening.value);
const listenWaveform = {
  levels: live.levels,
  level: live.audioLevel,
};

async function toggleListen() {
  if (isListening.value) {
    live.stop();
    return;
  }
  try {
    if (!micReady.value) await prepareMic();
    await live.start((blob) => {
      const next = new File([blob], "live-listen.wav", { type: "audio/wav" });
      file.value = next;
      emit("window", next);
    }, selectedMicId.value ?? undefined);
  } catch (e) {
    message.error(e instanceof Error ? e.message : "Could not start live listen");
  }
}
</script>

<template>
  <div class="audio-source">
    <div v-if="!source" class="source-choices">
      <button type="button" class="or-choice-card" @click="source = 'upload'">
        <span class="or-choice-card__title">Upload a clip</span>
        <span class="or-choice-card__desc">Use a voice recording you already have.</span>
      </button>
      <button type="button" class="or-choice-card" @click="source = 'record'">
        <span class="or-choice-card__title">Record with the microphone</span>
        <span class="or-choice-card__desc">Speak a short phrase and check it now.</span>
      </button>
      <button type="button" class="or-choice-card" @click="source = 'listen'">
        <span class="or-choice-card__title">Listen live</span>
        <span class="or-choice-card__desc">Keep the mic open. We’ll check every couple of seconds.</span>
      </button>
    </div>

    <div v-else class="source-switch-row">
      <NButton
        v-if="source !== 'upload'"
        text
        type="primary"
        class="source-switch"
        @click="source = 'upload'"
      >
        Upload a clip instead
      </NButton>
      <NButton
        v-if="source !== 'record'"
        text
        type="primary"
        class="source-switch"
        @click="source = 'record'"
      >
        Record a clip instead
      </NButton>
      <NButton
        v-if="source !== 'listen'"
        text
        type="primary"
        class="source-switch"
        @click="source = 'listen'"
      >
        Listen live instead
      </NButton>
    </div>

    <div v-if="source === 'upload'" class="source-panel">
      <NUpload
        v-model:file-list="fileList"
        :max="1"
        directory-dnd
        accept="audio/*,.wav,.mp3,.flac,.ogg,.m4a,.webm"
        :default-upload="false"
        :show-file-list="true"
        class="upload-area"
      >
        <NUploadDragger>
          <div class="dragger-inner">
            <NIcon size="36" :depth="3"><CloudUploadOutline /></NIcon>
            <p class="dragger-title">Drag an audio file here or click to browse</p>
            <p class="dragger-hint">WAV, MP3, FLAC, OGG, WebM — one file</p>
          </div>
        </NUploadDragger>
      </NUpload>
      <NTag v-if="file" size="small" type="success" :bordered="false" class="ready-tag">
        Ready: {{ file.name }}
      </NTag>
    </div>

    <div v-else-if="source === 'record'" class="source-panel source-panel--record">
      <NAlert
        v-if="!isSecureEnoughForMic()"
        type="warning"
        :bordered="false"
        title="HTTPS required for microphone"
        style="margin-bottom: 12px"
      >
        Use <strong>https://localhost:5173</strong> in dev, or serve the UI over HTTPS.
      </NAlert>

      <template v-else>
        <div class="record-toolbar">
          <NButton
            v-if="!micReady"
            type="primary"
            size="small"
            @click="prepareMic"
          >
            <template #icon>
              <NIcon><MicOutline /></NIcon>
            </template>
            Allow microphone
          </NButton>
          <NTag v-else size="small" type="success" :bordered="false">
            Microphone ready
          </NTag>
        </div>

        <div v-if="micReady && micOptions.length > 0" class="mic-picker">
          <label class="picker-label">Input device</label>
          <NSelect
            :value="selectedMicId"
            :options="micOptions"
            size="small"
            placeholder="Select microphone"
            @update:value="changeMicDevice"
          />
        </div>

        <VoiceWaveform v-if="isRecording" :source="waveformSource" />

        <div class="record-actions">
          <NButton
            :type="isRecording ? 'warning' : 'primary'"
            size="large"
            :loading="recordState === 'converting'"
            :disabled="!micReady && !isRecording"
            @click="toggleRecord"
          >
            <template #icon>
              <NIcon>
                <StopOutline v-if="isRecording" />
                <MicOutline v-else />
              </NIcon>
            </template>
            {{
              isRecording
                ? `Stop (${durationLabel})`
                : hasRecording
                  ? "Record again"
                  : "Start recording"
            }}
          </NButton>
          <NButton
            v-if="hasRecording"
            quaternary
            size="large"
            @click="playPreview"
          >
            <template #icon>
              <NIcon><PlayOutline /></NIcon>
            </template>
            Preview
          </NButton>
        </div>

        <p v-if="hasRecording" class="record-hint record-hint--ok">
          Recording saved — run the test when you are ready.
        </p>
        <p v-else-if="micReady" class="record-hint">
          Speak a short phrase (about 1–3 seconds), then stop.
        </p>
      </template>
    </div>

    <div v-else-if="source === 'listen'" class="source-panel source-panel--record">
      <NAlert
        v-if="!isSecureEnoughForMic()"
        type="warning"
        :bordered="false"
        title="HTTPS required for microphone"
        style="margin-bottom: 12px"
      >
        Use <strong>https://localhost:5173</strong> in dev, or serve the UI over HTTPS.
      </NAlert>

      <template v-else>
        <div class="record-toolbar">
          <NButton
            v-if="!micReady"
            type="primary"
            size="small"
            @click="prepareMic"
          >
            <template #icon>
              <NIcon><MicOutline /></NIcon>
            </template>
            Allow microphone
          </NButton>
          <NTag v-else size="small" :type="isListening ? 'warning' : 'success'" :bordered="false">
            {{ isListening ? "Listening" : "Microphone ready" }}
          </NTag>
        </div>

        <div v-if="micReady && micOptions.length > 0" class="mic-picker">
          <label class="picker-label">Input device</label>
          <NSelect
            :value="selectedMicId"
            :options="micOptions"
            size="small"
            placeholder="Select microphone"
            :disabled="isListening"
            @update:value="changeMicDevice"
          />
        </div>

        <VoiceWaveform v-if="isListening" :source="listenWaveform" />

        <div class="record-actions">
          <NButton
            :type="isListening ? 'warning' : 'primary'"
            size="large"
            :disabled="!micReady && !isListening"
            @click="toggleListen"
          >
            <template #icon>
              <NIcon>
                <StopOutline v-if="isListening" />
                <MicOutline v-else />
              </NIcon>
            </template>
            {{ isListening ? "Stop listening" : "Start listening" }}
          </NButton>
        </div>

        <p class="record-hint" :class="{ 'record-hint--ok': isListening }">
          {{
            isListening
              ? "Speak naturally. Results update as we hear you."
              : "We’ll send a short rolling window every couple of seconds."
          }}
        </p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.audio-source {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.source-choices {
  display: flex;
  flex-direction: column;
  gap: var(--or-inline-gap);
}

.source-switch-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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

.source-panel--record {
  display: flex;
  flex-direction: column;
  gap: 4px;
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

.ready-tag {
  margin-top: 12px;
}

.record-toolbar {
  margin-bottom: 4px;
}

.mic-picker {
  margin: 8px 0 4px;
  max-width: 320px;
}

.picker-label {
  display: block;
  margin-bottom: 6px;
  font-size: 0.75rem;
  color: var(--n-text-color-3);
}

.record-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}

.record-hint {
  margin: 10px 0 0;
  font-size: 0.8rem;
  color: var(--n-text-color-3);
}

.record-hint--ok {
  color: var(--n-primary-color);
}
</style>
