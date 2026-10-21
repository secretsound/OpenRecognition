import { onBeforeUnmount, readonly, ref, shallowRef } from "vue";
import { recordingBlobToWav } from "@/utils/audioWav";
import { attachStreamMeter, type MeterHandle } from "@/utils/audioMeter";
import { microphoneBlockedMessage } from "@/utils/secureContext";

export type RecorderState = "idle" | "recording" | "recorded" | "converting";

export function useVoiceRecorder() {
  const state = ref<RecorderState>("idle");
  const error = ref<string | null>(null);
  const durationMs = ref(0);
  const previewUrl = ref<string | null>(null);
  const wavBlob = ref<Blob | null>(null);
  const levels = ref<number[]>(Array.from({ length: 40 }, () => 0.04));
  const audioLevel = ref(0);
  const activeDeviceLabel = ref<string | null>(null);

  const micStream = shallowRef<MediaStream | null>(null);
  let mediaStream: MediaStream | null = null;
  let mediaRecorder: MediaRecorder | null = null;
  let chunks: BlobPart[] = [];
  let tickTimer: ReturnType<typeof setInterval> | null = null;
  let startedAt = 0;
  let meterHandle: MeterHandle | null = null;

  function clearPreview() {
    if (previewUrl.value) {
      URL.revokeObjectURL(previewUrl.value);
      previewUrl.value = null;
    }
    wavBlob.value = null;
  }

  function stopMeter() {
    meterHandle?.dispose();
    meterHandle = null;
    levels.value = Array.from({ length: 40 }, () => 0.04);
    audioLevel.value = 0;
  }

  function startMeter(stream: MediaStream) {
    stopMeter();
    const track = stream.getAudioTracks()[0];
    activeDeviceLabel.value = track?.label || "Default microphone";
    meterHandle = attachStreamMeter(stream, (nextLevels, peak) => {
      levels.value = nextLevels;
      audioLevel.value = peak;
    });
  }

  function stopTracks() {
    stopMeter();
    mediaStream?.getTracks().forEach((t) => t.stop());
    mediaStream = null;
    micStream.value = null;
    activeDeviceLabel.value = null;
  }

  function clearRecorderState() {
    if (tickTimer) {
      clearInterval(tickTimer);
      tickTimer = null;
    }
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      try {
        mediaRecorder.stop();
      } catch {
        /* ignore */
      }
    }
    mediaRecorder = null;
    chunks = [];
  }

  function releaseAll() {
    clearRecorderState();
    stopTracks();
  }

  async function ensureMic(
    deviceId?: string,
    options?: { meter?: boolean },
  ): Promise<void> {
    error.value = null;
    const enableMeter = options?.meter !== false;

    const needsNewStream =
      !mediaStream?.active ||
      (deviceId &&
        mediaStream.getAudioTracks()[0]?.getSettings().deviceId !== deviceId);

    if (mediaStream?.active && !needsNewStream) {
      const track = mediaStream.getAudioTracks()[0];
      activeDeviceLabel.value = track?.label || "Default microphone";
      if (enableMeter && !meterHandle) startMeter(mediaStream);
      if (!enableMeter) stopMeter();
      return;
    }

    if (mediaStream) {
      stopTracks();
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Microphone access is not supported in this browser.");
    }

    const audio: MediaTrackConstraints = {
      echoCancellation: true,
      noiseSuppression: false,
      autoGainControl: true,
      channelCount: 1,
    };
    if (deviceId) {
      audio.deviceId = { exact: deviceId };
    }

    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio });
      micStream.value = mediaStream;
      const track = mediaStream.getAudioTracks()[0];
      activeDeviceLabel.value = track?.label || "Default microphone";
      if (enableMeter) startMeter(mediaStream);
    } catch (e) {
      throw new Error(microphoneBlockedMessage(e));
    }
  }

  function pickMimeType(): string | undefined {
    const types = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/mp4",
    ];
    return types.find((t) => MediaRecorder.isTypeSupported(t));
  }

  async function start(): Promise<void> {
    clearPreview();
    error.value = null;
    clearRecorderState();

    await ensureMic(undefined, { meter: false });
    if (!mediaStream?.active) {
      throw new Error("Microphone not available — allow access and try again.");
    }
    startMeter(mediaStream);

    chunks = [];
    const mime = pickMimeType();
    try {
      mediaRecorder = mime
        ? new MediaRecorder(mediaStream, { mimeType: mime })
        : new MediaRecorder(mediaStream);
    } catch (e) {
      throw new Error(
        e instanceof Error ? e.message : "Could not start the recorder for this browser.",
      );
    }

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    mediaRecorder.onerror = () => {
      error.value = "Recording failed.";
      state.value = "idle";
    };

    mediaRecorder.onstop = async () => {
      if (tickTimer) {
        clearInterval(tickTimer);
        tickTimer = null;
      }
      const raw = new Blob(chunks, { type: mediaRecorder?.mimeType || "audio/webm" });
      chunks = [];
      if (raw.size < 200) {
        error.value = "Recording too short — try again.";
        state.value = "idle";
        return;
      }
      state.value = "converting";
      try {
        const wav = await recordingBlobToWav(raw);
        wavBlob.value = wav;
        previewUrl.value = URL.createObjectURL(wav);
        state.value = "recorded";
      } catch {
        error.value = "Could not process audio. Try again or upload a WAV file.";
        state.value = "idle";
      }
    };

    startedAt = Date.now();
    durationMs.value = 0;
    tickTimer = setInterval(() => {
      durationMs.value = Date.now() - startedAt;
    }, 100);

    mediaRecorder.start(200);
    state.value = "recording";
  }

  function stop(): void {
    if (mediaRecorder?.state === "recording") {
      mediaRecorder.stop();
      stopMeter();
    }
  }

  function setPreviewBlob(blob: Blob) {
    clearPreview();
    wavBlob.value = blob;
    previewUrl.value = URL.createObjectURL(blob);
    state.value = "recorded";
    error.value = null;
    durationMs.value = 0;
  }

  function discardTake() {
    clearRecorderState();
    clearPreview();
    error.value = null;
    durationMs.value = 0;
    state.value = "idle";
  }

  function reset() {
    releaseAll();
    clearPreview();
    error.value = null;
    durationMs.value = 0;
    state.value = "idle";
  }

  onBeforeUnmount(() => {
    releaseAll();
    clearPreview();
  });

  return {
    state,
    error,
    durationMs,
    previewUrl,
    wavBlob,
    levels,
    audioLevel,
    activeDeviceLabel,
    micStream: readonly(micStream),
    ensureMic,
    start,
    stop,
    reset,
    discardTake,
    releaseAll,
    setPreviewBlob,
  };
}
