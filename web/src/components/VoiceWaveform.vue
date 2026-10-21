<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, type Ref } from "vue";

/** Pass refs inside an object so Vue does not unwrap them in the template binding. */
export type WaveformSource = {
  levels: Ref<number[]>;
  level: Ref<number>;
};

const props = withDefaults(
  defineProps<{
    source: WaveformSource;
    active?: boolean;
  }>(),
  { active: true },
);

const canvasRef = ref<HTMLCanvasElement | null>(null);
let rafId = 0;

const isHearing = computed(() => props.active && props.source.level.value > 0.03);

const levelPct = computed(() => Math.round(props.source.level.value * 100));

const statusText = computed(() => {
  if (!props.active) return "Paused";
  if (isHearing.value) return `Receiving audio (${levelPct.value}%)`;
  return `Speak to test your mic (level ${levelPct.value}%)`;
});

function paint() {
  const canvas = canvasRef.value;
  if (canvas) {
    const ctx = canvas.getContext("2d");
    const lv = props.source.levels.value;
    if (ctx && lv.length > 0) {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      const w = Math.max(1, Math.floor(rect.width * dpr));
      const h = Math.max(1, Math.floor(rect.height * dpr));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      ctx.clearRect(0, 0, w, h);
      const gap = 2 * dpr;
      const barW = (w - gap * (lv.length - 1)) / lv.length;
      const mid = h / 2;
      const peak = props.source.level.value;

      for (let i = 0; i < lv.length; i++) {
        const raw = lv[i] ?? 0;
        const v = Math.min(1, Math.max(0, (raw - 0.04) / 0.96));
        const barH = Math.max(3 * dpr, v * h * 0.98);
        const x = i * (barW + gap);
        const y = mid - barH / 2;
        const active = props.active && (peak > 0.05 || raw > 0.08);
        ctx.fillStyle = active ? "#18a058" : "rgba(255, 255, 255, 0.2)";
        if (typeof ctx.roundRect === "function") {
          ctx.beginPath();
          ctx.roundRect(x, y, barW, barH, 2 * dpr);
          ctx.fill();
        } else {
          ctx.fillRect(x, y, barW, barH);
        }
      }
    }
  }
  rafId = requestAnimationFrame(paint);
}

onMounted(() => {
  rafId = requestAnimationFrame(paint);
});

onUnmounted(() => {
  if (rafId) cancelAnimationFrame(rafId);
});
</script>

<template>
  <div class="waveform" :class="{ 'waveform--hearing': isHearing }">
    <canvas ref="canvasRef" class="waveform-canvas" aria-hidden="true" />
    <p class="waveform-label">
      <span class="waveform-dot" />
      {{ statusText }}
    </p>
  </div>
</template>

<style scoped>
.waveform {
  margin: 16px 0;
  padding: 16px 18px 12px;
  border-radius: 10px;
  background: var(--n-color-modal);
  border: 1px solid var(--n-border-color);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.waveform--hearing {
  border-color: rgba(24, 160, 88, 0.45);
  box-shadow: 0 0 0 1px rgba(24, 160, 88, 0.12);
}

.waveform-canvas {
  display: block;
  width: 100%;
  height: 96px;
}

.waveform-label {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin: 10px 0 0;
  font-size: 0.8rem;
  color: var(--n-text-color-3);
}

.waveform--hearing .waveform-label {
  color: var(--n-primary-color);
}

.waveform-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--n-text-color-3);
}

.waveform--hearing .waveform-dot {
  background: var(--n-primary-color);
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.45;
    transform: scale(0.85);
  }
}
</style>
