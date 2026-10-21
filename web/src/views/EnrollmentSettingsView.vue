<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NAlert, NButton, NInput, NInputNumber, NSkeleton, NSlider, NSwitch, useMessage } from "naive-ui";
import { api, ApiError } from "@/api/client";
import type { EnrollmentOut } from "@/types/api";
import DetailHeader from "@/components/DetailHeader.vue";
import StatusPill from "@/components/StatusPill.vue";
import TypeTag from "@/components/TypeTag.vue";
import SettingsSection from "@/components/settings/SettingsSection.vue";
import SettingRow from "@/components/settings/SettingRow.vue";
import { useBreadcrumbOverride } from "@/composables/useBreadcrumbTail";

const route = useRoute();
const router = useRouter();
const message = useMessage();

const id = computed(() => route.params.id as string);
const loading = ref(true);
const saving = ref(false);
const enrollment = ref<EnrollmentOut | null>(null);

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
});

useBreadcrumbOverride(
  computed(() => {
    const en = enrollment.value;
    if (!en) return null;
    return [
      { label: "Library", to: "/enrollments" },
      { label: en.label, to: `/enrollments/${en.id}` },
      { label: "Settings" },
    ];
  }),
);

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
  };
}

const customConfidence = computed({
  get: () => draft.value.threshold != null,
  set: (on: boolean) => {
    draft.value.threshold = on ? (draft.value.threshold ?? 0.85) : null;
  },
});

const percent = computed(() =>
  draft.value.threshold == null ? 0 : Math.round(draft.value.threshold * 100),
);

const learnPercent = computed(() => Math.round(draft.value.learnMinConfidence * 100));
const marginPercent = computed(() => Math.round(draft.value.learnMargin * 100));

function closeEnough(a: number, b: number) {
  return Math.abs(a - b) < 0.001;
}

const dirty = computed(() => {
  const en = enrollment.value;
  if (!en) return false;
  const person = (en.external_ids?.homeassistant ?? "").trim();
  const threshold = en.threshold;
  const next = draft.value.threshold;
  const sameThreshold =
    (threshold == null && next == null) ||
    (threshold != null && next != null && Math.abs(threshold - next) < 0.001);
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

async function load() {
  loading.value = true;
  try {
    const en = await api<EnrollmentOut>(`/v1/enrollments/${id.value}`);
    enrollment.value = en;
    applyDraft(en);
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load");
    router.push("/enrollments");
  } finally {
    loading.value = false;
  }
}

function resetDraft() {
  if (enrollment.value) applyDraft(enrollment.value);
}

function onThreshold(value: number) {
  draft.value.threshold = value;
}

function onLearnConfidence(value: number) {
  draft.value.learnMinConfidence = value;
}

function onLearnMargin(value: number) {
  draft.value.learnMargin = value;
}

async function save() {
  const en = enrollment.value;
  if (!en || !canSave.value) return;
  saving.value = true;
  try {
    const external = { ...(en.external_ids ?? {}) };
    if (en.type === "person") {
      const person = draft.value.personId.trim();
      if (person) external.homeassistant = person;
      else delete external.homeassistant;
    }
    const updated = await api<EnrollmentOut>(`/v1/enrollments/${id.value}`, {
      method: "PATCH",
      json: {
        label: draft.value.label.trim(),
        enabled: draft.value.enabled,
        threshold: draft.value.threshold,
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
    enrollment.value = {
      ...en,
      ...updated,
      quality: updated.quality ?? en.quality,
      external_ids: updated.external_ids ?? external,
    };
    applyDraft(enrollment.value);
    message.success("Settings saved");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Save failed");
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="enrollment-settings">
    <NSkeleton v-if="loading" text :repeat="6" />

    <template v-else-if="enrollment">
      <DetailHeader
        title="Settings"
        description="Match rules for this name, including a stricter score and learning from sure voice matches."
      >
        <template #meta>
          <TypeTag :type="enrollment.type" />
          <StatusPill :enrollment="enrollment" />
        </template>
        <template #action>
          <NButton v-if="dirty" :disabled="saving" @click="resetDraft">Discard</NButton>
          <NButton type="primary" :loading="saving" :disabled="!canSave" @click="save">
            Save
          </NButton>
        </template>
      </DetailHeader>

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
              @update:value="onThreshold"
            />
          </div>
        </SettingsSection>

        <SettingsSection
          v-if="enrollment.type === 'person'"
          title="Keep learning"
          description="Save a voice clip when a match is sure enough, so this person stays current."
        >
          <SettingRow
            label="Learn from matches"
            hint="Wyoming can add a clip after the speech check. Practice runs on Try a match are never saved."
          >
            <NSwitch v-model:value="draft.learnEnabled" />
          </SettingRow>
          <div v-if="draft.learnEnabled" class="learn-options">
            <NAlert type="warning" :bordered="false">
              A confident mistake becomes part of this voice, and later matches can sound more like the wrong person. Learned clips show up with the other samples and can be removed.
            </NAlert>
            <div class="confidence">
              <div class="learn-label">Learn above</div>
              <p class="learn-hint">Only save a clip that scores at least this high.</p>
              <div class="confidence__value">{{ learnPercent }}%</div>
              <NSlider
                :value="draft.learnMinConfidence"
                :min="0.7"
                :max="0.99"
                :step="0.01"
                :tooltip="false"
                @update:value="onLearnConfidence"
              />
            </div>
            <div class="confidence">
              <div class="learn-label">Ahead of the next person</div>
              <p class="learn-hint">The match must beat the next person by this much.</p>
              <div class="confidence__value">{{ marginPercent }}%</div>
              <NSlider
                :value="draft.learnMargin"
                :min="0.02"
                :max="0.2"
                :step="0.01"
                :tooltip="false"
                @update:value="onLearnMargin"
              />
            </div>
            <SettingRow label="Per day" hint="Stop after this many new clips in a day.">
              <NInputNumber v-model:value="draft.learnDailyCap" :min="1" :max="50" />
            </SettingRow>
            <SettingRow
              label="Keep at most"
              hint="Older learned clips are removed so the list does not grow forever. Clips you added stay."
            >
              <NInputNumber v-model:value="draft.learnMaxSamples" :min="1" :max="100" />
            </SettingRow>
          </div>
        </SettingsSection>

        <SettingsSection
          v-if="enrollment.type === 'person'"
          title="Home Assistant"
          description="Wyoming can attach a transcript to this person. Leave blank to use the name match from Connections."
        >
          <NInput v-model:value="draft.personId" placeholder="person.luke" />
        </SettingsSection>
      </div>
    </template>
  </div>
</template>

<style scoped>
.enrollment-settings {
  display: flex;
  flex-direction: column;
  gap: var(--or-section-gap);
}

.settings-stack :deep(.settings-section + .settings-section) {
  margin-top: var(--or-section-gap);
}

.confidence {
  padding-top: 14px;
}

.confidence__value {
  margin-bottom: 8px;
  font-size: 1.5rem;
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
  font-size: 0.875rem;
  font-weight: 500;
}

.learn-hint {
  margin: 4px 0 8px;
  max-width: 520px;
  font-size: 0.8rem;
  line-height: 1.45;
  color: var(--n-text-color-3);
}
</style>
