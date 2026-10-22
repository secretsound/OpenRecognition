import { onBeforeUnmount, ref } from "vue";
import { encodeWav } from "@/utils/audioWav";
import { attachStreamMeter, type MeterHandle } from "@/utils/audioMeter";
import { microphoneBlockedMessage } from "@/utils/secureContext";

const TARGET_RATE = 16000;
const WINDOW_SEC = 2.5;
const HOP_SEC = 2.0;
const MIN_RMS = 0.012;

function flatten(chunks: Float32Array[], count: number): Float32Array {
  const out = new Float32Array(count);
  let offset = 0;
  for (const chunk of chunks) {
    const space = count - offset;
    if (space <= 0) break;
    const take = Math.min(chunk.length, space);
    out.set(chunk.subarray(0, take), offset);
    offset += take;
  }
  return out;
}

function rms(samples: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < samples.length; i++) {
    const s = samples[i] ?? 0;
    sum += s * s;
  }
  return Math.sqrt(sum / Math.max(1, samples.length));
}

function resample(input: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return input;
  const ratio = toRate / fromRate;
  const out = new Float32Array(Math.max(1, Math.round(input.length * ratio)));
  for (let i = 0; i < out.length; i++) {
    const src = i / ratio;
    const i0 = Math.min(input.length - 1, Math.floor(src));
    out[i] = input[i0] ?? 0;
  }
  return out;
}

export function useLiveListen() {
  const listening = ref(false);
  const error = ref<string | null>(null);
  const levels = ref<number[]>(Array.from({ length: 40 }, () => 0.04));
  const audioLevel = ref(0);

  let stream: MediaStream | null = null;
  let ctx: AudioContext | null = null;
  let processor: ScriptProcessorNode | null = null;
  let meter: MeterHandle | null = null;
  let pending: Float32Array[] = [];
  let pendingSamples = 0;
  let sinceHop = 0;
  let onWindow: ((blob: Blob) => void) | null = null;

  function stop() {
    processor?.disconnect();
    processor = null;
    meter?.dispose();
    meter = null;
    stream?.getTracks().forEach((t) => t.stop());
    stream = null;
    if (ctx) {
      void ctx.close();
      ctx = null;
    }
    pending = [];
    pendingSamples = 0;
    sinceHop = 0;
    listening.value = false;
  }

  async function start(cb: (blob: Blob) => void, deviceId?: string) {
    stop();
    error.value = null;
    onWindow = cb;
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Microphone access is not supported in this browser.");
    }
    const audio: MediaTrackConstraints = {
      echoCancellation: true,
      noiseSuppression: false,
      autoGainControl: true,
      channelCount: 1,
    };
    if (deviceId) audio.deviceId = { exact: deviceId };

    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio });
    } catch (e) {
      throw new Error(microphoneBlockedMessage(e));
    }

    ctx = new AudioContext();
    const source = ctx.createMediaStreamSource(stream);
    processor = ctx.createScriptProcessor(4096, 1, 1);
    const srcRate = ctx.sampleRate;
    const windowSamples = Math.floor(WINDOW_SEC * srcRate);
    const hopSamples = Math.floor(HOP_SEC * srcRate);

    processor.onaudioprocess = (e) => {
      const input = e.inputBuffer.getChannelData(0);
      const copy = new Float32Array(input);
      pending.push(copy);
      pendingSamples += copy.length;
      sinceHop += copy.length;
      while (pendingSamples - (pending[0]?.length ?? 0) >= windowSamples) {
        const dropped = pending.shift();
        if (dropped) pendingSamples -= dropped.length;
      }
      if (sinceHop < hopSamples || pendingSamples < windowSamples) return;
      sinceHop = 0;
      const raw = flatten(pending, windowSamples);
      if (rms(raw) < MIN_RMS) return;
      const wav = encodeWav(resample(raw, srcRate, TARGET_RATE), TARGET_RATE);
      onWindow?.(wav);
    };

    const mute = ctx.createGain();
    mute.gain.value = 0;
    source.connect(processor);
    processor.connect(mute);
    mute.connect(ctx.destination);
    meter = attachStreamMeter(stream, (next, peak) => {
      levels.value = next;
      audioLevel.value = peak;
    });
    listening.value = true;
  }

  onBeforeUnmount(stop);

  return { listening, error, levels, audioLevel, start, stop };
}
