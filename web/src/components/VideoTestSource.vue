<script setup lang="ts">
import { ref } from "vue";
import VideoClipper from "@/components/VideoClipper.vue";
import { DEFAULT_VIDEO_LIMITS, type VideoModalityChoice } from "@/utils/videoClip";

const model = defineModel<File | null>({ default: null });

const clipperRef = ref<InstanceType<typeof VideoClipper> | null>(null);

function getModality(): VideoModalityChoice {
  const exposed = clipperRef.value;
  if (!exposed) return "both";
  const m = exposed.modality as VideoModalityChoice | { value: VideoModalityChoice };
  if (typeof m === "string") return m;
  if (m && typeof m === "object" && "value" in m) return m.value;
  return "both";
}

defineExpose({ getModality });
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
