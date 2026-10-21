<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  NCard,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NButton,
  NUpload,
  NAlert,
  NSpace,
  NSteps,
  NStep,
  useMessage,
  useNotification,
} from "naive-ui";
import type { UploadFileInfo } from "naive-ui";
import {
  PersonOutline,
  PawOutline,
  CubeOutline,
  MusicalNotesOutline,
} from "@vicons/ionicons5";
import { NIcon } from "naive-ui";
import { apiForm } from "@/api/client";
import type { EnrollmentOut, EnrollmentType } from "@/types/api";
import AppPageHeader from "@/components/AppPageHeader.vue";
import { ApiError } from "@/api/client";
import { mediaConfigFor } from "@/utils/enrollmentMedia";
import { PET_SPECIES_OTHER, petSpeciesOptions } from "@/constants/petSpecies";

const router = useRouter();
const message = useMessage();
const notification = useNotification();

const wizardStep = ref(0);
const loading = ref(false);
const duplicateWarning = ref<string | null>(null);
const enrollmentType = ref<EnrollmentType>("person");
const enrollmentLabel = ref("");
const speciesSelect = ref<string | null>(null);
const speciesCustom = ref("");
const fileList = ref<UploadFileInfo[]>([]);
const preferGuidedAfterCreate = ref(true);

const typeOptions: { value: EnrollmentType; label: string; hint: string; icon: typeof PersonOutline }[] = [
  { value: "person", label: "Person", hint: "Voice and face, so you can match speech or a photo.", icon: PersonOutline },
  { value: "pet", label: "Pet", hint: "Photos of a specific animal.", icon: PawOutline },
  { value: "object", label: "Object", hint: "Photos of one thing you want to recognize.", icon: CubeOutline },
  { value: "sound", label: "Sound", hint: "Clips of a sound, like a doorbell or bark.", icon: MusicalNotesOutline },
];

const mediaConfig = computed(() => mediaConfigFor(enrollmentType.value));

const resolvedSpeciesHint = computed(() => {
  if (enrollmentType.value !== "pet" || !speciesSelect.value) return "";
  if (speciesSelect.value === PET_SPECIES_OTHER) return speciesCustom.value.trim();
  return speciesSelect.value;
});

const showSpeciesCustom = computed(
  () => enrollmentType.value === "pet" && speciesSelect.value === PET_SPECIES_OTHER,
);

const canAdvance = computed(() => {
  if (wizardStep.value === 0) return true;
  if (wizardStep.value === 1) return enrollmentLabel.value.trim().length > 0;
  return preferGuidedAfterCreate.value || fileList.value.some((f) => f.file);
});

watch(enrollmentType, () => {
  fileList.value = [];
  speciesSelect.value = null;
  speciesCustom.value = "";
});

function next() {
  if (wizardStep.value < 2) wizardStep.value += 1;
}

function back() {
  if (wizardStep.value > 0) wizardStep.value -= 1;
}

async function submit() {
  if (!enrollmentLabel.value.trim()) {
    message.warning("Label is required");
    return;
  }

  const files = fileList.value
    .map((f) => f.file)
    .filter((f): f is File => f != null);

  if (!preferGuidedAfterCreate.value && files.length === 0) {
    message.warning("Add at least one media file or choose guided capture after create");
    return;
  }

  loading.value = true;
  duplicateWarning.value = null;
  try {
    const form = new FormData();
    form.append("type", enrollmentType.value);
    form.append("label", enrollmentLabel.value.trim());
    if (resolvedSpeciesHint.value && enrollmentType.value === "pet") {
      form.append("species_hint", resolvedSpeciesHint.value);
    }
    form.append("enabled", "true");
    for (const f of files) {
      form.append("files", f);
    }
    const res = await apiForm<EnrollmentOut>("/v1/enrollments", form);
    if (res.duplicate_warning) {
      duplicateWarning.value = res.duplicate_warning;
    }
    notification.success({
      title: "Enrollment created",
      content:
        files.length > 0
          ? `${res.label} is ready with ${res.sample_count} sample(s).`
          : `${res.label} created — continue with guided capture.`,
    });
    router.push({
      path: `/enrollments/${res.id}`,
      query: preferGuidedAfterCreate.value ? { train: "1" } : undefined,
    });
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Enrollment failed");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div>
    <AppPageHeader
      title="New enrollment"
      description="Choose what you are adding, give it a name, then capture samples or upload files."
    />

    <NAlert
      v-if="duplicateWarning"
      type="warning"
      title="Possible duplicate"
      closable
      style="margin-bottom: var(--or-section-gap)"
      @close="duplicateWarning = null"
    >
      {{ duplicateWarning }}
    </NAlert>

    <NCard :bordered="false" class="wizard-card">
      <NSteps :current="wizardStep + 1" size="small" style="margin-bottom: 24px">
        <NStep title="Type" />
        <NStep title="Name" />
        <NStep title="Samples" />
      </NSteps>

      <div v-if="wizardStep === 0" class="step-pane">
        <p class="step-intro">What are you adding?</p>
        <div class="type-grid">
          <button
            v-for="opt in typeOptions"
            :key="opt.value"
            type="button"
            class="or-choice-card"
            :class="{ 'is-selected': enrollmentType === opt.value }"
            @click="enrollmentType = opt.value"
          >
            <NIcon :size="20"><component :is="opt.icon" /></NIcon>
            <span class="or-choice-card__title">{{ opt.label }}</span>
            <span class="or-choice-card__desc">{{ opt.hint }}</span>
          </button>
        </div>
      </div>

      <div v-else-if="wizardStep === 1" class="step-pane">
        <NForm label-placement="top">
          <NFormItem label="Name" required>
            <NInput v-model:value="enrollmentLabel" placeholder="For example, Luke or Pepper" />
          </NFormItem>
          <NFormItem v-if="enrollmentType === 'pet'" label="Species">
            <NSpace vertical :size="12" style="width: 100%">
              <NSelect
                v-model:value="speciesSelect"
                :options="petSpeciesOptions"
                placeholder="Select species (optional)"
                clearable
              />
              <NInput
                v-if="showSpeciesCustom"
                v-model:value="speciesCustom"
                placeholder="Enter species (e.g. ferret, guinea pig)"
              />
            </NSpace>
          </NFormItem>
        </NForm>
      </div>

      <div v-else-if="wizardStep === 2" class="step-pane">
        <p class="media-hint">{{ mediaConfig.hint }}</p>
        <div class="type-grid sample-choices">
          <button
            type="button"
            class="or-choice-card"
            :class="{ 'is-selected': preferGuidedAfterCreate }"
            @click="preferGuidedAfterCreate = true"
          >
            <span class="or-choice-card__title">Guided capture</span>
            <span class="or-choice-card__desc">Recommended. A short wizard collects the right samples after you create this.</span>
          </button>
          <button
            type="button"
            class="or-choice-card"
            :class="{ 'is-selected': !preferGuidedAfterCreate }"
            @click="preferGuidedAfterCreate = false"
          >
            <span class="or-choice-card__title">Upload files now</span>
            <span class="or-choice-card__desc">Use photos or clips you already have.</span>
          </button>
        </div>
        <template v-if="!preferGuidedAfterCreate">
          <p class="media-detail">{{ mediaConfig.detail }}</p>
          <NUpload
            v-model:file-list="fileList"
            multiple
            directory-dnd
            :accept="mediaConfig.accept"
            :default-upload="false"
            list-type="text"
          >
            <NButton>Choose files</NButton>
          </NUpload>
        </template>
        <p v-else class="media-detail">
          You will open the guided wizard on the enrollment page right after create.
        </p>
      </div>

      <div class="wizard-footer">
        <NButton v-if="wizardStep > 0" @click="back">Back</NButton>
        <span v-else />
        <NButton v-if="wizardStep < 2" type="primary" :disabled="!canAdvance" @click="next">
          Next
        </NButton>
        <NButton v-else type="primary" :loading="loading" :disabled="!canAdvance" @click="submit">
          Create
        </NButton>
      </div>
    </NCard>
  </div>
</template>

<style scoped>
.wizard-card {
  max-width: 720px;
}

.step-intro {
  margin: 0 0 16px;
  color: var(--n-text-color-2);
}

.type-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--or-inline-gap);
}

.sample-choices {
  margin-bottom: 16px;
}

.wizard-footer {
  display: flex;
  justify-content: space-between;
  gap: var(--or-inline-gap);
  margin-top: 24px;
}

.step-pane {
  min-height: 160px;
}

.media-hint {
  margin: 0 0 8px;
  color: var(--n-text-color-1);
  font-size: 0.9rem;
}

.media-detail {
  margin: 0 0 12px;
  color: var(--n-text-color-3);
  font-size: 0.8rem;
  line-height: 1.45;
}
</style>
