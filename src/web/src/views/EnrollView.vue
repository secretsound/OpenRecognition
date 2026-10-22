<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { NForm, NFormItem, NInput, NSelect, NButton, NSpace, NIcon, useMessage, useNotification } from "naive-ui";
import { PersonOutline, PawOutline, CubeOutline, MusicalNotesOutline } from "@vicons/ionicons5";
import { apiForm, ApiError } from "@/api/client";
import type { EnrollmentOut, EnrollmentType } from "@/types/api";
import PageHeader from "@/components/kit/PageHeader.vue";
import ChoiceCard from "@/components/kit/ChoiceCard.vue";
import { PET_SPECIES_OTHER, petSpeciesOptions } from "@/constants/petSpecies";

const router = useRouter();
const message = useMessage();
const notification = useNotification();

const loading = ref(false);
const enrollmentType = ref<EnrollmentType>("person");
const enrollmentLabel = ref("");
const speciesSelect = ref<string | null>(null);
const speciesCustom = ref("");

const typeOptions: { value: EnrollmentType; label: string; hint: string; icon: typeof PersonOutline }[] = [
  { value: "person", label: "Person", hint: "Voice and face, so you can match speech or a photo.", icon: PersonOutline },
  { value: "pet", label: "Pet", hint: "Photos of a specific animal.", icon: PawOutline },
  { value: "object", label: "Object", hint: "Photos of one thing you want to recognize.", icon: CubeOutline },
  { value: "sound", label: "Sound", hint: "Clips of a sound, like a doorbell or bark.", icon: MusicalNotesOutline },
];

const resolvedSpeciesHint = computed(() => {
  if (enrollmentType.value !== "pet" || !speciesSelect.value) return "";
  if (speciesSelect.value === PET_SPECIES_OTHER) return speciesCustom.value.trim();
  return speciesSelect.value;
});

const showSpeciesCustom = computed(
  () => enrollmentType.value === "pet" && speciesSelect.value === PET_SPECIES_OTHER,
);

const canCreate = computed(() => enrollmentLabel.value.trim().length > 0);

watch(enrollmentType, () => {
  speciesSelect.value = null;
  speciesCustom.value = "";
});

async function submit() {
  if (!canCreate.value) {
    message.warning("A name is required");
    return;
  }
  loading.value = true;
  try {
    const form = new FormData();
    form.append("type", enrollmentType.value);
    form.append("label", enrollmentLabel.value.trim());
    if (resolvedSpeciesHint.value && enrollmentType.value === "pet") {
      form.append("species_hint", resolvedSpeciesHint.value);
    }
    form.append("enabled", "true");
    const res = await apiForm<EnrollmentOut>("/v1/enrollments", form);
    notification.success({
      title: "Created",
      content: `${res.label} is ready for samples.`,
    });
    router.push({ path: `/enrollments/${res.id}`, query: { tab: "samples", teach: "1" } });
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not create this");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="or-page or-page--prose">
    <PageHeader
      title="Add someone or something"
      description="Choose a type, give it a name, then you'll add samples on the next screen."
    />

    <div class="or-choice-grid">
      <ChoiceCard
        v-for="opt in typeOptions"
        :key="opt.value"
        :title="opt.label"
        :description="opt.hint"
        :selected="enrollmentType === opt.value"
        @select="enrollmentType = opt.value"
      >
        <template #icon>
          <NIcon :size="20"><component :is="opt.icon" /></NIcon>
        </template>
      </ChoiceCard>
    </div>

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

    <div class="create-row">
      <NButton @click="router.push('/enrollments')">Cancel</NButton>
      <NButton type="primary" :loading="loading" :disabled="!canCreate" @click="submit">
        Create
      </NButton>
    </div>
  </div>
</template>

<style scoped>
.create-row {
  display: flex;
  justify-content: flex-end;
  gap: var(--or-space-3);
}
</style>
