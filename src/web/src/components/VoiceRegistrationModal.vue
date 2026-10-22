<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  NButton,
  NSpace,
  NAlert,
  NProgress,
  NIcon,
  NSelect,
  NSpin,
  useMessage,
} from "naive-ui";
import GuidedCaptureModal from "@/components/GuidedCaptureModal.vue";
import type { SelectOption } from "naive-ui";
import { MicOutline, StopOutline, PlayOutline } from "@vicons/ionicons5";
import { api, apiForm, ApiError } from "@/api/client";
import type { EnrollmentOut, EnrollmentType, SampleOut, SamplePreviewOut } from "@/types/api";
import { useVoiceRecorder } from "@/composables/useVoiceRecorder";
import {
  pickVoicePhrases,
  soundPrompts,
  VOICE_DELIVERY_COACH,
  type VoicePrompt,
  type VoiceSessionMode,
} from "@/constants/voicePhrases";
import { isSecureEnoughForMic } from "@/utils/secureContext";
import {
  analyzeTakeLocally,
  issueLabel,
  mergeTakeQuality,
  type TakeQuality,
} from "@/utils/takeQuality";
import VoiceWaveform from "@/components/VoiceWaveform.vue";
import ConfidenceMeter from "@/components/kit/ConfidenceMeter.vue";

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

const phrases = ref<VoicePrompt[]>(soundPrompts());
const sessionMode = ref<VoiceSessionMode>("core");
const phraseOffset = ref(0);
const loadingSession = ref(false);

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
const phraseQuality = ref<(TakeQuality | null)[]>([]);
const scoringTake = ref(false);
let takeSeq = 0;

const phraseIndex = computed(() => step.value - 2);
const currentPrompt = computed(() => {
  const i = phraseIndex.value;
  return i >= 0 && i < phrases.value.length ? phrases.value[i] : null;
});

const currentCoach = computed(() => {
  const delivery = currentPrompt.value?.delivery ?? "natural";
  return VOICE_DELIVERY_COACH[delivery];
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

const isSound = computed(() => props.enrollmentType === "sound");

/** Speaker embeddings need a few seconds of speech, not a clipped word. */
const minRecordMs = computed(() => (isSound.value ? 2000 : 2500));
const recommendMs = computed(() => (isSound.value ? 3500 : 4000));
const maxRecordMs = 15000;

const takeLength = computed<"short" | "ok" | "good" | "long">(() => {
  const ms = recorder.durationMs.value;
  if (ms < minRecordMs.value) return "short";
  if (ms < recommendMs.value) return "ok";
  if (ms <= 8000) return "good";
  return "long";
});

const takeHint = computed(() => {
  if (recorder.state.value !== "recorded") return "";
  if (takeLength.value === "ok" || takeLength.value === "short") {
    return "A little short — re-record if you cut off the last words. Four to six seconds is better.";
  }
  return "";
});

const modalTitle = computed(() => {
  if (isSound.value) return `Sound enrollment — ${props.enrollmentLabel}`;
  if (sessionMode.value === "improve") return `Improve voice — ${props.enrollmentLabel}`;
  if (sessionMode.value === "encore") return `Practice voice — ${props.enrollmentLabel}`;
  return `Voice training — ${props.enrollmentLabel}`;
});

const introCopy = computed(() => {
  if (isSound.value) {
    return {
      lead: `We will capture ${phrases.value.length} clips of the same sound so the model hears a consistent event.`,
      tips: [
        "Keep the source at a similar distance each time.",
        "A few seconds of the real sound is better than one long noisy file.",
        "Recordings stay on this device until you finish.",
      ],
    };
  }
  if (sessionMode.value === "improve") {
    return {
      lead: `These ${phrases.value.length} sentences are new, and each one changes how you talk to a speaker — next to you, quieter, or calling from across the room.`,
      tips: [
        "Follow the note on each phrase. You are talking to the device, not pretending to be it.",
        "Stay yourself — no character voice.",
        "Finish the whole sentence. Four to six seconds still matters.",
      ],
    };
  }
  if (sessionMode.value === "encore") {
    return {
      lead: `You have already recorded the full phrase bank. This pass repeats lines at different distances so the profile keeps up with how you actually call a speaker.`,
      tips: [
        "Use the note shown — same words, closer to the device or from across the room.",
        "Finish each sentence. Short clips are the usual reason scores stall around 50%.",
        "You can stop after this set and try Recognize again.",
      ],
    };
  }
  return {
    lead: `We will record ${phrases.value.length} short sentences so the model hears vowels, consonants, and numbers — and how you talk to a speaker from different distances.`,
    tips: [
      "Use a quiet room. Hold the mic about 20–30 cm away unless a phrase asks you to call from farther back.",
      "Most lines are your normal voice. A few ask you to talk to a speaker on the table, or call one from across the room.",
      "You are talking to the device, not trying to sound like it. Stay natural.",
      "Each phrase should last about four to six seconds. Nothing is uploaded until you finish.",
    ],
  };
});

function resetWizard() {
  step.value = 0;
  micReady.value = false;
  uploading.value = false;
  uploadDone.value = false;
  phraseBlobs.value = Array.from({ length: phrases.value.length }, () => null);
  phraseQuality.value = Array.from({ length: phrases.value.length }, () => null);
  scoringTake.value = false;
  recorder.reset();
}

async function loadSession() {
  loadingSession.value = true;
  try {
    if (isSound.value) {
      phrases.value = soundPrompts();
      sessionMode.value = "core";
      phraseOffset.value = 0;
      return;
    }
    const samples = await api<SampleOut[]>(`/v1/enrollments/${props.enrollmentId}/samples`);
    const audio = samples.filter((s) => s.modality === "audio");
    const used = audio
      .map((s) => s.phrase_text)
      .filter((text): text is string => Boolean(text));
    const picked = pickVoicePhrases(used);
    phrases.value = picked.phrases;
    sessionMode.value = picked.mode;
    phraseOffset.value = audio.length;
  } catch {
    const picked = pickVoicePhrases([]);
    phrases.value = picked.phrases;
    sessionMode.value = picked.mode;
    phraseOffset.value = 0;
  } finally {
    phraseBlobs.value = Array.from({ length: phrases.value.length }, () => null);
    phraseQuality.value = Array.from({ length: phrases.value.length }, () => null);
    loadingSession.value = false;
  }
}

watch(
  () => props.show,
  (open) => {
    if (open) {
      resetWizard();
      void loadSession();
    } else {
      recorder.reset();
    }
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

const currentQuality = computed(() => {
  const i = phraseIndex.value;
  return i >= 0 ? phraseQuality.value[i] ?? null : null;
});

const weakTakes = computed(() =>
  phraseQuality.value
    .map((q, i) => ({ i, q }))
    .filter((row): row is { i: number; q: TakeQuality } => row.q?.verdict === "retry"),
);

function setPhraseQuality(index: number, quality: TakeQuality | null) {
  const next = [...phraseQuality.value];
  while (next.length <= index) next.push(null);
  next[index] = quality;
  phraseQuality.value = next;
}

async function scoreCurrentTake(blob: Blob) {
  const index = phraseIndex.value;
  if (index < 0) return;
  const seq = ++takeSeq;
  scoringTake.value = true;
  try {
    const local = await analyzeTakeLocally(blob);
    if (seq !== takeSeq) return;
    setPhraseQuality(index, local);
    const form = new FormData();
    form.append("file", new File([blob], "take.wav", { type: "audio/wav" }));
    const remote = await apiForm<SamplePreviewOut>(
      `/v1/enrollments/${props.enrollmentId}/samples/preview`,
      form,
    );
    if (seq !== takeSeq) return;
    setPhraseQuality(index, mergeTakeQuality(local, remote));
  } catch {
    /* Local score is enough if the preview call fails. */
  } finally {
    if (seq === takeSeq) scoringTake.value = false;
  }
}

watch(
  () => [recorder.state.value, recorder.wavBlob.value] as const,
  ([state, blob]) => {
    if (!isPhraseStep.value) return;
    if (state === "recorded" && blob) {
      if (phraseQuality.value[phraseIndex.value]) return;
      void scoreCurrentTake(blob);
    }
    if (state !== "recorded" && state !== "converting") {
      takeSeq += 1;
      scoringTake.value = false;
    }
  },
);

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
    if (recorder.durationMs.value < minRecordMs.value) {
      message.warning("Hold a little longer — finish the whole sentence");
      return;
    }
    recorder.stop();
    return;
  }
  if (recorder.state.value === "recorded") {
    setPhraseQuality(phraseIndex.value, null);
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
    const meta = phrases.value.map((prompt, i) => ({
      source: "voice_wizard",
      phrase_index: phraseOffset.value + i,
      phrase_text: prompt.text,
      original_filename: `voice-phrase-${phraseOffset.value + i + 1}.wav`,
      content_type: "audio/wav",
    }));
    form.append("sample_meta", JSON.stringify(meta));
    blobs.forEach((blob, i) => {
      if (blob) {
        form.append(
          "files",
          new File([blob], `voice-phrase-${phraseOffset.value + i + 1}.wav`, {
            type: "audio/wav",
          }),
        );
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
    if (currentQuality.value?.verdict === "retry") {
      message.warning("That take is weak — you can re-record it, or continue and replace it later.");
    }

    if (phraseIndex.value + 1 >= phrases.value.length) {
      step.value = totalSteps.value - 1;
      const weak =
        currentQuality.value?.verdict === "retry" ||
        phraseQuality.value.some((q) => q?.verdict === "retry");
      if (weak) {
        message.warning("Some takes scored low. Re-record them or upload anyway.");
        return;
      }
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
  const q = phraseQuality.value[i];
  if (q?.verdict === "retry") return "Redo";
  if (q?.verdict === "keep") return "Good take";
  if (phraseBlobs.value[i]) return "Saved";
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
    :title="modalTitle"
    :steps="wizardSteps"
    :current="step"
    layout="progress"
    @update:show="emit('update:show', $event)"
  >
    <div v-if="loadingSession" class="step-body step-body--center">
      <NSpin size="small" />
      <p class="hint">Choosing phrases you have not recorded yet…</p>
    </div>

    <div v-else-if="isIntro" class="step-body">
      <p class="lead">{{ introCopy.lead }}</p>
      <ul class="tips">
        <li v-for="tip in introCopy.tips" :key="tip">{{ tip }}</li>
      </ul>
    </div>

    <div v-else-if="isMicStep" class="step-body">
      <p class="lead">Allow microphone access so we can capture the samples.</p>
      <NAlert
        v-if="!isSecureEnoughForMic()"
        type="warning"
        title="HTTPS required for microphone"
        style="margin-bottom: 16px"
      >
        This page is not a secure context. Open the UI over HTTPS on localhost
        (for example <strong>https://localhost:5173</strong>).
        Set <code>OPENRECOGNITION_WEB_ORIGIN</code> on the API to match.
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
      <p class="delivery-title">{{ currentCoach.title }}</p>
      <blockquote class="phrase">{{ currentPrompt?.text }}</blockquote>
      <p class="hint">
        {{ currentCoach.hint }} Aim for four to six seconds.
        Nothing is sent until you finish all {{ phrases.length }} phrases.
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
        <span
          v-if="recorder.state.value === 'recording' || recorder.state.value === 'recorded'"
          class="duration"
          :class="`duration--${takeLength}`"
        >
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
        :status="takeLength === 'good' ? 'success' : takeLength === 'ok' ? 'warning' : 'info'"
        style="margin-top: 12px"
      />
      <p v-if="recorder.state.value === 'recording'" class="duration-coach">
        {{
          takeLength === "short"
            ? "Keep going — finish the sentence"
            : takeLength === "ok"
              ? "Good start — a couple more words if you can"
              : takeLength === "good"
                ? "Nice length — stop when you finish"
                : "Long enough — you can stop"
        }}
      </p>
      <NAlert
        v-if="takeHint"
        type="warning"
        :bordered="false"
        style="margin-top: 12px"
      >
        {{ takeHint }}
      </NAlert>

      <div
        v-if="recorder.state.value === 'recorded' || scoringTake || currentQuality"
        class="take-score"
        :class="currentQuality ? `take-score--${currentQuality.verdict}` : ''"
      >
        <div class="take-score__head">
          <p class="or-caps">This take</p>
          <span v-if="scoringTake" class="or-muted or-small">Checking…</span>
          <span v-else-if="currentQuality" class="or-muted or-small">
            {{ currentQuality.verdict === "keep" ? "Looks good" : "Re-record this one" }}
          </span>
        </div>
        <ConfidenceMeter
          v-if="currentQuality"
          :value="currentQuality.score"
          :threshold="0.55"
          size="sm"
        />
        <p v-if="currentQuality?.fit != null" class="take-score__fit">
          Match to this voice {{ Math.round(currentQuality.fit * 100) }}%
        </p>
        <p v-if="currentQuality" class="take-score__advice">{{ currentQuality.advice }}</p>
        <ul v-if="currentQuality?.issues.length" class="take-score__issues">
          <li v-for="issue in currentQuality.issues" :key="issue">{{ issueLabel(issue) }}</li>
        </ul>
      </div>
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
        Quality updates automatically. You can record another set, add photos, or try Recognize.
      </p>
      <NAlert
        v-else-if="weakTakes.length && !uploading"
        type="warning"
        :bordered="false"
        style="margin-top: 12px"
        title="Some takes should be recorded again"
      >
        Phrases
        {{ weakTakes.map((row) => row.i + 1).join(", ") }}
        scored low. Use Back to replace them before uploading.
      </NAlert>
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
            :disabled="loadingSession || (isPhraseStep && !canProceedFromPhrase)"
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
            {{ weakTakes.length ? "Upload anyway" : "Retry upload" }}
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

.step-body--center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
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

.delivery-title {
  margin: 0 0 8px;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--n-text-color-1);
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

.duration--short {
  color: var(--n-warning-color);
}

.duration--good {
  color: var(--n-success-color);
}

.duration-coach {
  margin: 8px 0 0;
  font-size: 0.8rem;
  color: var(--n-text-color-3);
}

.take-score {
  width: 100%;
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: var(--or-radius-md);
  border: 1px solid var(--or-line);
  background: var(--or-surface-sunken, transparent);
}

.take-score--keep {
  border-color: color-mix(in oklab, var(--n-success-color) 45%, var(--or-line));
}

.take-score--retry {
  border-color: color-mix(in oklab, var(--n-warning-color) 55%, var(--or-line));
}

.take-score__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.take-score__fit,
.take-score__advice {
  margin: 8px 0 0;
  font-size: 0.85rem;
  color: var(--n-text-color-2);
}

.take-score__issues {
  margin: 8px 0 0;
  padding-left: 1.1rem;
  color: var(--n-text-color-3);
  font-size: 0.8rem;
  line-height: 1.45;
}
</style>
