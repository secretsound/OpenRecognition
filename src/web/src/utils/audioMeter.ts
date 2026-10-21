/** Attach a level meter to a mic stream; returns a dispose function. */

const BAR_COUNT = 40;

export type MeterHandle = {
  dispose: () => void;
  getContext: () => AudioContext | null;
};

const IDLE = 0.04;
const ATTACK = 0.72;
const RELEASE = 0.06;

function smooth(current: number, target: number): number {
  const rate = target > current ? ATTACK : RELEASE;
  return current + (target - current) * rate;
}

function rawBars(timeData: Float32Array, peak: number): number[] {
  const bars: number[] = [];
  const slice = Math.max(1, Math.floor(timeData.length / BAR_COUNT));

  for (let i = 0; i < BAR_COUNT; i++) {
    let barPeak = 0;
    const start = i * slice;
    const end = Math.min(timeData.length, start + slice);
    for (let j = start; j < end; j++) {
      barPeak = Math.max(barPeak, Math.abs(timeData[j] ?? 0));
    }
    const curved = Math.min(1, Math.pow(barPeak * 2.8, 0.55));
    bars.push(Math.max(IDLE, curved * Math.max(peak, 0.15)));
  }
  return bars;
}

export function attachStreamMeter(
  stream: MediaStream,
  onUpdate: (levels: number[], peak: number) => void,
): MeterHandle {
  const track = stream.getAudioTracks()[0];
  if (!track) {
    onUpdate(Array.from({ length: BAR_COUNT }, () => 0.04), 0);
    return { dispose: () => {}, getContext: () => null };
  }

  const ctx = new AudioContext({ latencyHint: "interactive" });
  const source = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  analyser.smoothingTimeConstant = 0.82;
  analyser.minDecibels = -90;
  analyser.maxDecibels = -10;

  const mute = ctx.createGain();
  mute.gain.value = 0;

  source.connect(analyser);
  analyser.connect(mute);
  mute.connect(ctx.destination);

  const timeData = new Float32Array(analyser.fftSize);
  const freqData = new Uint8Array(analyser.frequencyBinCount);
  const displayBars = Array.from({ length: BAR_COUNT }, () => IDLE);
  let displayPeak = 0;
  let rafId = 0;
  let disposed = false;

  const tick = () => {
    if (disposed) return;
    if (ctx.state === "suspended") {
      void ctx.resume();
    }

    analyser.getFloatTimeDomainData(timeData);
    analyser.getByteFrequencyData(freqData);

    let sumSq = 0;
    for (let i = 0; i < timeData.length; i++) {
      const s = timeData[i] ?? 0;
      sumSq += s * s;
    }
    const rms = Math.sqrt(sumSq / timeData.length);

    let freqPeak = 0;
    const voiceBinEnd = Math.min(60, freqData.length);
    for (let i = 1; i < voiceBinEnd; i++) {
      freqPeak = Math.max(freqPeak, (freqData[i] ?? 0) / 255);
    }

    const peak = Math.min(1, Math.max(rms * 8, freqPeak * 1.4));
    const next = rawBars(timeData, peak);
    for (let i = 0; i < BAR_COUNT; i++) {
      displayBars[i] = smooth(displayBars[i] ?? IDLE, next[i] ?? IDLE);
    }
    displayPeak = smooth(displayPeak, peak);
    onUpdate([...displayBars], displayPeak);

    rafId = requestAnimationFrame(tick);
  };

  void ctx.resume().then(() => {
    if (!disposed) rafId = requestAnimationFrame(tick);
  });

  return {
    dispose() {
      disposed = true;
      if (rafId) cancelAnimationFrame(rafId);
      source.disconnect();
      analyser.disconnect();
      mute.disconnect();
      void ctx.close();
    },
    getContext: () => ctx,
  };
}
