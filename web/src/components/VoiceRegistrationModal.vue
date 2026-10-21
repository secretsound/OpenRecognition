<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  NButton,
  NSpace,
  NAlert,
  NProgress,
  NIcon,
  NSelect,
  useMessage,
} from "naive-ui";
import GuidedCaptureModal from "@/components/GuidedCaptureModal.vue";
import type { SelectOption } from "naive-ui";
import { MicOutline, StopOutline, PlayOutline } from "@vicons/ionicons5";
import { apiForm } from "@/api/client";
import type { EnrollmentOut, EnrollmentType } from "@/types/api";
import { ApiError } from "@/api/client";
import { useVoiceRecorder } from "@/composables/useVoiceRecorder";
import {
  VOICE_ENROLLMENT_PHRASES,
  SOUND_ENROLLMENT_PHRASES,
} from "@/constants/voicePhrases";
import { isSecureEnoughForMic } from "@/utils/secureContext";
import VoiceWaveform from "@/components/VoiceWaveform.vue";

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
const recorder = useVoiceRecorder();

/** Refs wrapped in a plain object so child components can read live meter data. */
const waveformSource = {
  levels: recorder.levels,
  level: recorder.audioLevel,
};

const phrases = computed(() =>
  props.enrollmentType === "sound"
    ? [...SOUND_ENROLLMENT_PHRASES]
    : [...VOICE_ENROLLMENT_PHRASES],
);

/** 0 intro, 1 mic, 2..phrases+1 record, last = done */
const totalSteps = computed(() => 2 + phrases.value.length + 1);
const step = ref(0);
const micReady = ref(false);
const micDevices = ref<MediaDeviceInfo[]>([]);
const selectedMicId = ref<string | null>(null);
const uploading = ref(false);
const uploadDone = ref(false);

/** Local WAV blobs per phrase — uploaded only when wizard finishes. */
const phraseBlobs = ref<(Blob | null)[]>([]);

const phraseIndex = computed(() => step.value - 2);
const currentPhrase = computed(() => {
  const i = phraseIndex.value;
  return i >= 0 && i < phrases.value.length ? phrases.value[i] : "";
});

const isIntro = computed(() => step.value === 0);
const isMicStep = computed(() => step.value === 1);
const isPhraseStep = computed(
  () => step.value >= 2 && step.value < 2 + phrases.value.length,
);
const isDone = computed(() => step.value === totalSteps.value - 1);

const recordedCount = computed(
  () => phraseBlobs.value.filter((b) => b != null).length,
);

const canProceedFromPhrase = computed(
  () => recorder.state.value === "recorded" && recorder.wavBlob.value != null,
);

const showWaveform = computed(
  () => micReady.value && (isMicStep.value || isPhraseStep.value),
);

const micOptions = computed<SelectOption[]>(() =>
  micDevices.value.map((d) => ({
    label: d.label || `Microphone (${d.deviceId.slice(0, 8)}…)`,
    value: d.deviceId,
  })),
);

const micSilent = computed(() => micReady.value && recorder.audioLevel.value < 0.04);

const minRecordMs = 1500;
const maxRecordMs = 12000;

function resetWizard() {
  step.value = 0;
  micReady.value = false;
  uploading.value = false;
  uploadDone.value = false;
  phraseBlobs.value = Array.from({ length: phrases.value.length }, () => null);
  recorder.reset();
}

watch(
  () => props.show,
  (open) => {
    if (open) resetWizard();
    else recorder.reset();
  },
);

watch(
  () => recorder.durationMs.value,
  (ms) => {
    if (recorder.state.value === "recording" && ms >= maxRecordMs) {
      recorder.stop();
    }
  },
);

watch([step, phraseIndex], () => {
  if (!isPhraseStep.value || phraseIndex.value < 0) return;
  const saved = phraseBlobs.value[phraseIndex.value];
  if (saved) {
    recorder.setPreviewBlob(saved);
  } else {
    recorder.discardTake();
  }
});

function close() {
  emit("update:show", false);
}

async function refreshMicDevices() {
  const devices = await navigator.mediaDevices.enumerateDevices();
  micDevices.value = devices.filter((d) => d.kind === "audioinput");
}

async function prepareMic() {
  try {
    await recorder.ensureMic(selectedMicId.value ?? undefined);
    await refreshMicDevices();
    const track = recorder.micStream.value?.getAudioTracks()[0];
    const currentId = track?.getSettings().deviceId;
    if (currentId) selectedMicId.value = currentId;
    micReady.value = true;
    message.success("Microphone ready");
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Microphone permission denied";
    message.error(msg);
  }
}

async function changeMicDevice(deviceId: string) {
  try {
    await recorder.ensureMic(deviceId);
    selectedMicId.value = deviceId;
    micReady.value = true;
    message.success("Microphone switched");
  } catch (e) {
    message.error(e instanceof Error ? e.message : "Could not open microphone");
  }
}

async function toggleRecord() {
  if (recorder.state.value === "recording") {
    if (recorder.durationMs.value < minRecordMs) {
      message.warning("Hold the button a little longer (at least 1.5 seconds)");
      return;
    }
    recorder.stop();
    return;
  }
  if (recorder.state.value === "recorded") {
    recorder.discardTake();
  }
  try {
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

function savePhraseLocally(): boolean {
  const blob = recorder.wavBlob.value;
  if (!blob) return false;
  const idx = phraseIndex.value;
  const next = [...phraseBlobs.value];
  while (next.length <= idx) next.push(null);
  next[idx] = blob;
  phraseBlobs.value = next;
  return true;
}

async function uploadAllPhrases(): Promise<boolean> {
  const blobs = phraseBlobs.value;
  if (blobs.length < phrases.value.length || blobs.some((b) => !b)) {
    message.warning("Record every phrase before finishing");
    return false;
  }

  uploading.value = true;
  try {
    const form = new FormData();
    const meta = phrases.value.map((phraseText, i) => ({
      source: "voice_wizard",
      phrase_index: i,
      phrase_text: phraseText,
      original_filename: `voice-phrase-${i + 1}.wav`,
      content_type: "audio/wav",
    }));
    form.append("sample_meta", JSON.stringify(meta));
    blobs.forEach((blob, i) => {
      if (blob) {
        form.append("files", new File([blob], `voice-phrase-${i + 1}.wav`, { type: "audio/wav" }));
      }
    });
    const updated = await apiForm<EnrollmentOut>(
      `/v1/enrollments/${props.enrollmentId}/samples`,
      form,
    );
    uploadDone.value = true;
    emit("completed", updated);
    message.success("Voice samples uploaded");
    return true;
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Upload failed");
    return false;
  } finally {
    uploading.value = false;
  }
}

async function next() {
  if (isIntro.value) {
    step.value = 1;
    return;
  }
  if (isMicStep.value) {
    if (!micReady.value) {
      await prepareMic();
      if (!micReady.value) return;
    }
    step.value = 2;
    return;
  }
  if (isPhraseStep.value) {
    if (!canProceedFromPhrase.value) {
      message.warning("Record this phrase before continuing");
      return;
    }
    if (!savePhraseLocally()) return;

    if (phraseIndex.value + 1 >= phrases.value.length) {
      step.value = totalSteps.value - 1;
      await uploadAllPhrases();
    } else {
      step.value += 1;
    }
    return;
  }
  close();
}

function back() {
  if (step.value <= 0) return;
  if (isPhraseStep.value && canProceedFromPhrase.value) {
    savePhraseLocally();
  } else if (isPhraseStep.value) {
    recorder.discardTake();
  }
  step.value -= 1;
}

function formatDuration(ms: number): string {
  const s = Math.floor(ms / 1000);
  const tenths = Math.floor((ms % 1000) / 100);
  return `${s}.${tenths}s`;
}

function phraseStepDescription(i: number): string | undefined {
  if (phraseBlobs.value[i]) return "Saved locally";
  if (isPhraseStep.value && phraseIndex.value === i && recorder.state.value === "recorded") {
    return "Recorded";
  }
  return undefined;
}

const wizardSteps = computed(() => [
  { title: "Intro", description: "How it works" },
  { title: "Microphone", description: "Permissions" },
  ...phrases.value.map((_, i) => ({
    title: `Phrase ${i + 1}`,
    description: phraseStepDescription(i),
  })),
  { title: "Complete", description: uploadDone.value ? "Uploaded" : "Review" },
]);
</script>

<template>
  <GuidedCaptureModal
    :show="show"
    :title="`Voice enrollment — ${enrollmentLabel}`"
    :steps="wizardSteps"
    :current="step"
    @update:show="emit('update:show', $event)"
  >
        <div v-if="isIntro" class="step-body">
          <p class="lead">
            We will record <strong>{{ phrases.length }} short phrases</strong> to build a voice
            profile for speaker recognition.
          </p>
          <ul class="tips">
            <li>Use a quiet room and hold the mic about 20–30 cm away.</li>
            <li>Speak naturally at a normal volume — same as you would when identified later.</li>
            <li>
              Each phrase covers different sounds (vowels, consonants, numbers) so the model learns
              your full voice, not just one sentence.
            </li>
            <li>
              Recordings stay on this device until you finish — use <strong>Back</strong> to
              re-record any phrase before uploading.
            </li>
          </ul>
        </div>

        <div v-else-if="isMicStep" class="step-body">
          <p class="lead">Allow microphone access so we can capture your voice samples.</p>
          <NAlert
            v-if="!isSecureEnoughForMic()"
            type="warning"
            title="HTTPS required for microphone"
            style="margin-bottom: 16px"
          >
            This page is not a secure context. Run the UI with
            <code>npm run dev</code> in <code>web/</code> and open
            <strong>https://localhost:5173</strong> (not http:// on a remote host).
            Set <code>OPENRECOGNITION_WEB_ORIGIN=https://localhost:5173</code> on the API.
          </NAlert>
      <NButton :disabled="micReady" @click="prepareMic">
        <template #icon>
          <NIcon><MicOutline /></NIcon>
        </template>
        {{ micReady ? "Microphone ready" : "Allow microphone" }}
      </NButton>
      <div v-if="micReady && micOptions.length > 0" class="mic-picker">
        <label class="picker-label">Input device</label>
        <NSelect
          :value="selectedMicId"
          :options="micOptions"
          placeholder="Select microphone"
          @update:value="changeMicDevice"
        />
        <p v-if="recorder.activeDeviceLabel" class="device-name">
          Active: {{ recorder.activeDeviceLabel }}
        </p>
      </div>
      <VoiceWaveform v-if="showWaveform" :source="waveformSource" />
      <NAlert
        v-if="micReady && micSilent"
        type="warning"
        :bordered="false"
        style="margin-top: 12px"
        title="No audio detected"
      >
        The level stays at 0% — try another device above, speak louder, or check that the
        browser has permission to use your microphone in system settings.
      </NAlert>
      <p v-else-if="micReady" class="ok-hint">
        Speak and watch the bars move, then continue to the phrases.
      </p>
        </div>

        <div v-else-if="isPhraseStep" class="step-body">
          <p class="step-label">Phrase {{ phraseIndex + 1 }} of {{ phrases.length }}</p>
          <blockquote class="phrase">{{ currentPhrase }}</blockquote>
          <p class="hint">
            Read the phrase aloud, then tap stop. Nothing is sent to the server until you finish
            all {{ phrases.length }} phrases.
          </p>

          <NAlert
            v-if="phraseBlobs[phraseIndex]"
            type="info"
            :bordered="false"
            style="margin-bottom: 12px"
          >
            You have a saved take for this phrase. Record again to replace it.
          </NAlert>

          <NAlert v-if="recorder.error.value" type="error" style="margin-bottom: 12px">
            {{ recorder.error.value }}
          </NAlert>

          <VoiceWaveform v-if="showWaveform" :source="waveformSource" />

          <div class="record-row">
            <NButton
              :type="recorder.state.value === 'recording' ? 'warning' : 'primary'"
              size="large"
              :loading="recorder.state.value === 'converting'"
              @click="toggleRecord"
            >
              <template #icon>
                <NIcon>
                  <StopOutline v-if="recorder.state.value === 'recording'" />
                  <MicOutline v-else />
                </NIcon>
              </template>
              {{
                recorder.state.value === "recording"
                  ? "Stop"
                  : recorder.state.value === "recorded"
                    ? "Re-record"
                    : "Record"
              }}
            </NButton>
            <span v-if="recorder.state.value === 'recording'" class="duration">
              {{ formatDuration(recorder.durationMs.value) }}
            </span>
            <NButton
              v-if="recorder.state.value === 'recorded'"
              quaternary
              @click="playPreview"
            >
              <template #icon>
                <NIcon><PlayOutline /></NIcon>
              </template>
              Play back
            </NButton>
          </div>

          <NProgress
            v-if="recorder.state.value === 'recording'"
            type="line"
            :percentage="Math.min(100, (recorder.durationMs.value / maxRecordMs) * 100)"
            :show-indicator="false"
            status="info"
            style="margin-top: 12px"
          />
        </div>

        <div v-else-if="isDone" class="step-body">
          <NAlert
            v-if="uploadDone"
            type="success"
            title="Voice samples saved"
          >
            Uploaded {{ recordedCount }} phrase recording{{ recordedCount === 1 ? "" : "s" }} for
            <strong>{{ enrollmentLabel }}</strong>.
          </NAlert>
          <NAlert v-else-if="uploading" type="info" title="Uploading…">
            Sending {{ recordedCount }} recordings to the server.
          </NAlert>
          <NAlert v-else type="warning" title="Upload incomplete">
            Something went wrong. Use Back to review your phrases and try again.
          </NAlert>
          <p v-if="uploadDone" class="hint" style="margin-top: 12px">
            Use Check quality on the enrollment page, then try a match with a new voice clip.
          </p>
          <NProgress
            v-if="uploadDone"
            type="line"
            :percentage="100"
            :indicator-placement="'inside'"
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
            :loading="uploading || recorder.state.value === 'converting'"
            :disabled="isPhraseStep && !canProceedFromPhrase"
            @click="next"
          >
            {{
              isPhraseStep
                ? phraseIndex + 1 >= phrases.length
                  ? "Finish & upload"
                  : "Next phrase"
                : "Continue"
            }}
          </NButton>
          <NButton v-else-if="uploadDone" type="primary" @click="close">Done</NButton>
          <NButton v-else type="primary" :loading="uploading" @click="uploadAllPhrases">
            Retry upload
          </NButton>
        </NSpace>
      </NSpace>
    </template>
  </GuidedCaptureModal>
</template>

<style scoped>
.step-body {
  min-height: 220px;
}

.lead {
  margin: 0 0 16px;
  line-height: 1.55;
  color: var(--n-text-color-1);
}

.tips {
  margin: 0;
  padding-left: 1.25rem;
  color: var(--n-text-color-2);
  line-height: 1.6;
  font-size: 0.9rem;
}

.step-label {
  margin: 0 0 8px;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--n-text-color-3);
}

.phrase {
  margin: 0 0 16px;
  padding: 20px 24px;
  font-size: 1.25rem;
  line-height: 1.5;
  font-weight: 500;
  border-left: 4px solid var(--n-primary-color);
  background: rgba(24, 160, 88, 0.08);
  border-radius: 0 8px 8px 0;
}

.hint {
  margin: 0 0 16px;
  font-size: 0.85rem;
  color: var(--n-text-color-3);
}

.ok-hint {
  margin: 12px 0 0;
  font-size: 0.875rem;
  color: var(--n-primary-color);
}

.mic-picker {
  margin-top: 16px;
  max-width: 360px;
}

.picker-label {
  display: block;
  margin-bottom: 6px;
  font-size: 0.8rem;
  color: var(--n-text-color-3);
}

.device-name {
  margin: 8px 0 0;
  font-size: 0.75rem;
  color: var(--n-text-color-3);
}

.record-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.duration {
  font-variant-numeric: tabular-nums;
  font-size: 1.1rem;
  color: var(--n-text-color-2);
}


</style>
