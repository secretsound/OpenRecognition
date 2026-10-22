<script setup lang="ts">
import { ref } from "vue";
import VideoClipper from "@/components/VideoClipper.vue";
import { DEFAULT_VIDEO_LIMITS, type VideoModalityChoice } from "@/utils/videoClip";

const model = defineModel<File | null>({ default: null });

const clipperRef = ref<InstanceType<typeof VideoClipper> | null>(null);

function unwrapNum(value: number | { value: number } | undefined): number {
  if (typeof value === "number") return value;
  if (value && typeof value === "object" && "value" in value) return value.value;
  return 0;
}

function getModality(): VideoModalityChoice {
  const exposed = clipperRef.value;
  if (!exposed) return "both";
  const m = exposed.modality as VideoModalityChoice | { value: VideoModalityChoice };
  if (typeof m === "string") return m;
  if (m && typeof m === "object" && "value" in m) return m.value;
  return "both";
}

function getClipDuration(): number {
  return unwrapNum(clipperRef.value?.clipDurationSec as number | { value: number } | undefined);
}

defineExpose({ getModality, getClipDuration });
</script>

<template>
  <VideoClipper
    ref="clipperRef"
    v-model="model"
    mode="test"
    :limits="DEFAULT_VIDEO_LIMITS"
    :show-modality-choice="true"
  />
</template>
