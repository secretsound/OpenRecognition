<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NAlert, NInput, NInputNumber, NSlider, NSwitch, useMessage } from "naive-ui";
import { api, ApiError } from "@/api/client";
import type { EnrollmentOut } from "@/types/api";
import SettingsSection from "@/components/settings/SettingsSection.vue";
import SettingRow from "@/components/settings/SettingRow.vue";
import StickySaveBar from "@/components/kit/StickySaveBar.vue";
import { useUnsavedGuard } from "@/composables/useUnsaved";

const props = defineProps<{
  enrollment: EnrollmentOut;
}>();

const emit = defineEmits<{
  updated: [enrollment: EnrollmentOut];
}>();

const message = useMessage();
const saving = ref(false);

const draft = ref({
  label: "",
  enabled: true,
  threshold: null as number | null,
  personId: "",
  learnEnabled: false,
  learnMinConfidence: 0.9,
  learnMargin: 0.05,
  learnDailyCap: 8,
  learnMaxSamples: 20,
  wyomingMinConfidence: null as number | null,
});

function applyDraft(en: EnrollmentOut) {
  draft.value = {
    label: en.label,
    enabled: en.enabled,
    threshold: en.threshold,
    personId: en.external_ids?.homeassistant ?? "",
    learnEnabled: en.learn_enabled ?? false,
    learnMinConfidence: en.learn_min_confidence ?? 0.9,
    learnMargin: en.learn_margin ?? 0.05,
    learnDailyCap: en.learn_daily_cap ?? 8,
    learnMaxSamples: en.learn_max_samples ?? 20,
    wyomingMinConfidence: en.wyoming_min_confidence ?? null,
  };
}

watch(
  () => props.enrollment.id,
  () => applyDraft(props.enrollment),
  { immediate: true },
);

const customConfidence = computed({
  get: () => draft.value.threshold != null,
  set: (on: boolean) => {
    draft.value.threshold = on ? (draft.value.threshold ?? 0.85) : null;
  },
});

const customWyoming = computed({
  get: () => draft.value.wyomingMinConfidence != null,
  set: (on: boolean) => {
    draft.value.wyomingMinConfidence = on ? (draft.value.wyomingMinConfidence ?? 0.75) : null;
  },
});

const percent = computed(() =>
  draft.value.threshold == null ? 0 : Math.round(draft.value.threshold * 100),
);

const wyomingPercent = computed(() =>
  draft.value.wyomingMinConfidence == null
    ? 0
    : Math.round(draft.value.wyomingMinConfidence * 100),
);

const learnPercent = computed(() => Math.round(draft.value.learnMinConfidence * 100));
const marginPercent = computed(() => Math.round(draft.value.learnMargin * 100));

function closeEnough(a: number, b: number) {
  return Math.abs(a - b) < 0.001;
}

const dirty = computed(() => {
  const en = props.enrollment;
  const person = (en.external_ids?.homeassistant ?? "").trim();
  const threshold = en.threshold;
  const next = draft.value.threshold;
  const sameThreshold =
    (threshold == null && next == null) ||
    (threshold != null && next != null && Math.abs(threshold - next) < 0.001);
  const savedWyoming = en.wyoming_min_confidence ?? null;
  const nextWyoming = draft.value.wyomingMinConfidence;
  const sameWyoming =
    (savedWyoming == null && nextWyoming == null) ||
    (savedWyoming != null &&
      nextWyoming != null &&
      Math.abs(savedWyoming - nextWyoming) < 0.001);
  const learnChanged =
    en.type === "person" &&
    (draft.value.learnEnabled !== (en.learn_enabled ?? false) ||
      !closeEnough(draft.value.learnMinConfidence, en.learn_min_confidence ?? 0.9) ||
      !closeEnough(draft.value.learnMargin, en.learn_margin ?? 0.05) ||
      draft.value.learnDailyCap !== (en.learn_daily_cap ?? 8) ||
      draft.value.learnMaxSamples !== (en.learn_max_samples ?? 20));
  return (
    draft.value.label.trim() !== en.label ||
    draft.value.enabled !== en.enabled ||
    !sameThreshold ||
    !sameWyoming ||
    (en.type === "person" && draft.value.personId.trim() !== person) ||
    learnChanged
  );
});

const canSave = computed(
  () =>
    dirty.value &&
    draft.value.label.trim().length > 0 &&
    draft.value.learnDailyCap != null &&
    draft.value.learnMaxSamples != null,
);

useUnsavedGuard(dirty);

function resetDraft() {
  applyDraft(props.enrollment);
}

async function save() {
  const en = props.enrollment;
  if (!canSave.value) return;
  saving.value = true;
  try {
    const external = { ...(en.external_ids ?? {}) };
    if (en.type === "person") {
      const person = draft.value.personId.trim();
      if (person) external.homeassistant = person;
      else delete external.homeassistant;
    }
    const updated = await api<EnrollmentOut>(`/v1/enrollments/${en.id}`, {
      method: "PATCH",
      json: {
        label: draft.value.label.trim(),
        enabled: draft.value.enabled,
        threshold: draft.value.threshold,
        wyoming_min_confidence: draft.value.wyomingMinConfidence,
        ...(en.type === "person"
          ? {
              external_ids: external,
              learn_enabled: draft.value.learnEnabled,
              learn_min_confidence: draft.value.learnMinConfidence,
              learn_margin: draft.value.learnMargin,
              learn_daily_cap: draft.value.learnDailyCap,
              learn_max_samples: draft.value.learnMaxSamples,
            }
          : {}),
      },
    });
    const next = {
      ...en,
      ...updated,
      quality: updated.quality ?? en.quality,
      external_ids: updated.external_ids ?? external,
    };
    applyDraft(next);
    emit("updated", next);
    message.success("Settings saved");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Save failed");
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="settings-stack">
    <SettingsSection title="Name" description="Shown in the library and in transcripts.">
      <NInput v-model:value="draft.label" placeholder="Name" />
    </SettingsSection>

    <SettingsSection title="Recognition">
      <SettingRow label="Included in matching" hint="When off, this name is skipped.">
        <NSwitch v-model:value="draft.enabled" />
      </SettingRow>
      <SettingRow
        label="Custom match confidence"
        hint="Turn this on to require a higher score for this name only. A lower number does not make a match easier than the server minimum."
      >
        <NSwitch v-model:value="customConfidence" />
      </SettingRow>
      <div v-if="draft.threshold != null" class="confidence">
        <div class="confidence__value">{{ percent }}%</div>
        <NSlider
          :value="draft.threshold"
          :min="0.5"
          :max="0.99"
          :step="0.01"
          :tooltip="false"
          @update:value="(v: number) => (draft.threshold = v)"
        />
        <p class="or-muted or-small">
          Matches for this name must reach {{ percent }}%. This only raises the bar.
        </p>
      </div>
    </SettingsSection>

    <SettingsSection
      v-if="enrollment.type === 'person'"
      title="Keep learning"
      description="Save a voice clip when a match is sure enough, so this person stays current."
    >
      <SettingRow
        label="Learn from matches"
        hint="Wyoming can add a clip after the speech check. Practice runs on Recognize are never saved."
      >
        <NSwitch v-model:value="draft.learnEnabled" />
      </SettingRow>
      <div v-if="draft.learnEnabled" class="learn-options">
        <NAlert type="warning" :bordered="false">
          A confident mistake becomes part of this voice. Learned clips can be removed from Samples.
        </NAlert>
        <div class="confidence">
          <div class="learn-label">Learn above</div>
          <p class="or-muted or-small">Only save a clip that scores at least this high.</p>
          <div class="confidence__value">{{ learnPercent }}%</div>
          <NSlider
            :value="draft.learnMinConfidence"
            :min="0.7"
            :max="0.99"
            :step="0.01"
            :tooltip="false"
            @update:value="(v: number) => (draft.learnMinConfidence = v)"
          />
        </div>
        <div class="confidence">
          <div class="learn-label">Ahead of the next person</div>
          <p class="or-muted or-small">The match must beat the next person by this much.</p>
          <div class="confidence__value">{{ marginPercent }}%</div>
          <NSlider
            :value="draft.learnMargin"
            :min="0.02"
            :max="0.2"
            :step="0.01"
            :tooltip="false"
            @update:value="(v: number) => (draft.learnMargin = v)"
          />
        </div>
        <SettingRow label="Per day" hint="Stop after this many new clips in a day.">
          <NInputNumber v-model:value="draft.learnDailyCap" :min="1" :max="50" />
        </SettingRow>
        <SettingRow
          label="Keep at most"
          hint="Older learned clips are removed. Clips you added stay."
        >
          <NInputNumber v-model:value="draft.learnMaxSamples" :min="1" :max="100" />
        </SettingRow>
      </div>
    </SettingsSection>

    <SettingsSection
      v-if="enrollment.type === 'person'"
      title="Wyoming"
      description="When Assist should treat this person as a match. Use a lower number if their microphone is noisy."
    >
      <SettingRow
        label="Custom inclusion"
        hint="Turn this on to set a bar just for Wyoming. Leave it off to use the server default."
      >
        <NSwitch v-model:value="customWyoming" />
      </SettingRow>
      <div v-if="draft.wyomingMinConfidence != null" class="confidence">
        <div class="confidence__value">{{ wyomingPercent }}%</div>
        <NSlider
          :value="draft.wyomingMinConfidence"
          :min="0.3"
          :max="0.99"
          :step="0.01"
          :tooltip="false"
          @update:value="(v: number) => (draft.wyomingMinConfidence = v)"
        />
        <p class="or-muted or-small">
          Wyoming includes this person at {{ wyomingPercent }}%. A lower number is easier to trigger.
        </p>
      </div>
    </SettingsSection>

    <SettingsSection
      v-if="enrollment.type === 'person'"
      title="Home Assistant"
      description="Wyoming can attach a transcript to this person. Leave blank to use the name match from Connections."
    >
      <NInput v-model:value="draft.personId" placeholder="person.luke" />
    </SettingsSection>

    <StickySaveBar :dirty="dirty" :saving="saving" :can-save="canSave" @save="save" @discard="resetDraft" />
  </div>
</template>

<style scoped>
.settings-stack :deep(.settings-section + .settings-section) {
  margin-top: var(--or-section-gap);
}

.confidence {
  padding-top: 14px;
}

.confidence__value {
  margin-bottom: 8px;
  font-size: var(--or-text-title);
  font-weight: 600;
  letter-spacing: -0.02em;
}

.learn-options {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 16px;
}

.learn-label {
  font-size: var(--or-text-body);
  font-weight: 500;
}
</style>
