<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NAlert,
  NDropdown,
  NModal,
  useDialog,
  useMessage,
} from "naive-ui";
import type { DropdownOption } from "naive-ui";
import type { UploadFileInfo } from "naive-ui";
import { api, apiForm, ApiError } from "@/api/client";
import type { EnrollmentOut, QualityInfo } from "@/types/api";
import PageHeader from "@/components/kit/PageHeader.vue";
import SegmentedControl from "@/components/kit/SegmentedControl.vue";
import ProfileMark from "@/components/kit/ProfileMark.vue";
import TimeAgo from "@/components/kit/TimeAgo.vue";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import StatusPill from "@/components/StatusPill.vue";
import TypeTag from "@/components/TypeTag.vue";
import QualityBreakdown from "@/components/QualityBreakdown.vue";
import EnrollmentSamplesPanel from "@/components/EnrollmentSamplesPanel.vue";
import AddSamplesPanel from "@/components/AddSamplesPanel.vue";
import VoiceRegistrationModal from "@/components/VoiceRegistrationModal.vue";
import FaceEnrollmentModal from "@/components/FaceEnrollmentModal.vue";
import PhotoEnrollmentModal from "@/components/PhotoEnrollmentModal.vue";
import VideoEnrollmentModal from "@/components/VideoEnrollmentModal.vue";
import EnrollmentSettingsForm from "@/components/EnrollmentSettingsForm.vue";
import EnrollmentActivityPanel from "@/components/EnrollmentActivityPanel.vue";
import TestModalityDialog from "@/components/TestModalityDialog.vue";
import { resolveTestModalityFor, type TestModality } from "@/utils/testModality";
import { useBreadcrumbTail } from "@/composables/useBreadcrumbTail";
import { pct } from "@/utils/confidence";
import { canWrite } from "@/utils/roles";
import { useAuth } from "@/composables/useAuth";
import { useEventStream } from "@/composables/useEventStream";

type Tab = "overview" | "samples" | "activity" | "settings";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const { role, canAddSamples, canManageEnrollment } = useAuth();

const id = computed(() => route.params.id as string);
const loading = ref(true);
const enrollment = ref<EnrollmentOut | null>(null);
const evaluating = ref(false);
const deleting = ref(false);
const uploading = ref(false);
const samplesPanelRef = ref<InstanceType<typeof EnrollmentSamplesPanel> | null>(null);
const showTestChooser = ref(false);
const fileList = ref<UploadFileInfo[]>([]);
const showVoiceWizard = ref(false);
const showFaceWizard = ref(false);
const showPhotoWizard = ref(false);
const showVideoWizard = ref(false);

const testedKey = computed(() => `or-tested-${id.value}`);
const tested = ref(false);

useBreadcrumbTail(computed(() => enrollment.value?.label));

const canTeach = computed(() => canAddSamples(enrollment.value?.id));
const canManage = computed(() => canManageEnrollment(enrollment.value?.id));

const tab = computed<Tab>({
  get() {
    const t = route.query.tab;
    if (t === "settings" && !canManage.value) return "overview";
    if (t === "samples" || t === "activity" || t === "settings") return t;
    return "overview";
  },
  set(next) {
    router.replace({ query: { ...route.query, tab: next === "overview" ? undefined : next } });
  },
});

const teaching = computed(() => route.query.teach === "1" || route.query.train === "1");

const tabOptions = computed(() => {
  const tabs: { value: Tab; label: string }[] = [
    { value: "overview", label: "Overview" },
    { value: "samples", label: "Samples" },
    { value: "activity", label: "Activity" },
  ];
  if (canManage.value) tabs.push({ value: "settings", label: "Settings" });
  return tabs;
});

async function evaluateQuality(silent = false) {
  if (!enrollment.value) return;
  evaluating.value = true;
  try {
    const q = await api<QualityInfo>(`/v1/enrollments/${id.value}/evaluate`, { method: "POST" });
    enrollment.value = { ...enrollment.value, quality: q };
    if (!silent) message.success("Quality updated");
  } catch (e) {
    if (!silent) message.error(e instanceof ApiError ? e.message : "Evaluate failed");
  } finally {
    evaluating.value = false;
  }
}

async function load() {
  loading.value = true;
  try {
    enrollment.value = await api<EnrollmentOut>(`/v1/enrollments/${id.value}`);
    tested.value = sessionStorage.getItem(testedKey.value) === "1";
    if (enrollment.value.sample_count > 0 && !enrollment.value.quality) {
      await evaluateQuality(true);
    }
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load");
    router.push("/enrollments");
  } finally {
    loading.value = false;
  }
}

useEventStream((event) => {
  const log = event.log;
  if (!log || event.type !== "recognition.log") return;
  const current = enrollment.value;
  if (!current) return;
  const matches =
    log.entity_id === current.id ||
    (!!log.label && log.label.toLowerCase() === current.label.toLowerCase());
  if (!matches) return;
  if (log.event === "recognition.match" && !log.dry_run) {
    enrollment.value = { ...current, last_seen_at: log.created_at };
  }
});

async function toggleEnabled(v: boolean) {
  if (!enrollment.value) return;
  try {
    enrollment.value = await api<EnrollmentOut>(`/v1/enrollments/${id.value}`, {
      method: "PATCH",
      json: { enabled: v },
    });
    message.success(v ? "Turned on" : "Turned off");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Update failed");
    await load();
  }
}

function pushTest(modality: TestModality) {
  if (!enrollment.value) return;
  router.push({
    name: "test",
    query: {
      expect: enrollment.value.label,
      modality,
      enrollmentId: enrollment.value.id,
    },
  });
}

async function goRecognize() {
  if (!enrollment.value) return;
  const choice = await resolveTestModalityFor(enrollment.value);
  if (choice === "choose") {
    showTestChooser.value = true;
    return;
  }
  pushTest(choice);
}

function openTeach() {
  router.replace({ query: { ...route.query, tab: "samples", teach: "1" } });
}

function closeTeach() {
  const query = { ...route.query };
  delete query.teach;
  delete query.train;
  router.replace({ query });
}

const moreOptions = computed<DropdownOption[]>(() => {
  if (!enrollment.value) return [];
  const options: DropdownOption[] = [];
  if (canManage.value) {
    options.push({ label: enrollment.value.enabled ? "Turn off" : "Turn on", key: "toggle" });
  }
  if (canWrite(role.value)) {
    if (options.length) options.push({ type: "divider", key: "d" });
    options.push({ label: "Delete", key: "delete" });
  }
  return options;
});

async function onMore(key: string) {
  if (key === "toggle" && enrollment.value) await toggleEnabled(!enrollment.value.enabled);
  else if (key === "delete") {
    dialog.warning({
      title: "Delete this?",
      content: "Samples and the name are removed. This cannot be undone.",
      positiveText: "Delete",
      negativeText: "Cancel",
      onPositiveClick: () => remove(),
    });
  }
}

async function onSamplesUpdated(updated: EnrollmentOut) {
  enrollment.value = updated;
  await evaluateQuality(true);
}

async function addFiles() {
  const files = fileList.value.map((f) => f.file).filter((f): f is File => f != null);
  if (!files.length) {
    message.warning("Select files to upload");
    return;
  }
  uploading.value = true;
  try {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    const updated = await apiForm<EnrollmentOut>(`/v1/enrollments/${id.value}/samples`, form);
    fileList.value = [];
    enrollment.value = updated;
    samplesPanelRef.value?.reload();
    await evaluateQuality(true);
    message.success(`${updated.sample_count} samples now`);
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Upload failed");
  } finally {
    uploading.value = false;
  }
}

async function afterWizard(title: string, updated: EnrollmentOut) {
  enrollment.value = updated;
  samplesPanelRef.value?.reload();
  await evaluateQuality(true);
  message.success(`${title}. Quality updated.`);
}

async function remove() {
  deleting.value = true;
  try {
    await api(`/v1/enrollments/${id.value}`, { method: "DELETE" });
    message.success("Deleted");
    router.push("/enrollments");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Delete failed");
  } finally {
    deleting.value = false;
  }
}

const lastSeen = computed(() => enrollment.value?.last_seen_at ?? null);

onMounted(async () => {
  await load();
  if (route.query.train === "1") {
    router.replace({ query: { ...route.query, train: undefined, tab: "samples", teach: "1" } });
  }
});
</script>

<template>
  <div class="or-page">
    <ContentSkeleton v-if="loading" variant="detail" />

    <template v-else-if="enrollment">
      <PageHeader :title="enrollment.label" description="Samples teach this server who or what to recognize.">
        <template #lead>
          <ProfileMark :label="enrollment.label" :type="enrollment.type" size="xl" />
        </template>
        <template #meta>
          <TypeTag :type="enrollment.type" />
          <StatusPill :enrollment="enrollment" />
          <span class="or-muted or-small">{{ enrollment.sample_count }} samples</span>
          <span v-if="enrollment.quality" class="or-muted or-small">
            Quality {{ pct(enrollment.quality.score) }}
          </span>
        </template>
        <template #action>
          <NButton v-if="canTeach" type="primary" @click="openTeach">Add samples</NButton>
          <NButton @click="goRecognize">Recognize</NButton>
          <NDropdown v-if="moreOptions.length" :options="moreOptions" @select="onMore">
            <NButton :loading="deleting">More</NButton>
          </NDropdown>
        </template>
        <template #tabs>
          <SegmentedControl v-model="tab" aria-label="Profile sections" :options="tabOptions" />
        </template>
      </PageHeader>

      <TestModalityDialog
        :show="showTestChooser"
        :label="enrollment.label"
        @update:show="showTestChooser = $event"
        @pick="pushTest"
      />

      <NAlert
        v-if="enrollment.duplicate_warning && tab === 'overview'"
        type="warning"
        title="This may be a duplicate"
        size="small"
        :bordered="false"
      >
        {{ enrollment.duplicate_warning }}
      </NAlert>

      <section v-if="tab === 'overview'" class="detail-grid">
        <div class="or-stack">
          <div v-if="!tested || !enrollment.quality?.usable" class="or-surface or-surface--md">
            <p class="or-caps">Setup</p>
            <ol class="setup">
              <li :class="{ done: enrollment.sample_count > 0 }">Add samples</li>
              <li :class="{ done: enrollment.quality?.usable }">Quality looks good</li>
              <li :class="{ done: tested }">Recognize once</li>
            </ol>
          </div>
          <section v-if="enrollment.quality">
            <h2 class="or-heading" style="margin-bottom: 12px">Quality</h2>
            <QualityBreakdown :quality="enrollment.quality" />
          </section>
        </div>
        <aside class="or-surface or-surface--md about">
          <p class="or-caps">About</p>
          <dl>
            <div>
              <dt>ID</dt>
              <dd class="or-mono">{{ enrollment.id }}</dd>
            </div>
            <div v-if="enrollment.species_hint">
              <dt>Species</dt>
              <dd>{{ enrollment.species_hint }}</dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>{{ enrollment.model_version ?? "—" }}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd><TimeAgo :value="enrollment.created_at" /></dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd><TimeAgo :value="enrollment.updated_at" /></dd>
            </div>
            <div v-if="lastSeen">
              <dt>Last seen</dt>
              <dd><TimeAgo :value="lastSeen" /></dd>
            </div>
          </dl>
        </aside>
      </section>

      <section v-else-if="tab === 'samples'" class="or-stack">
        <EnrollmentSamplesPanel
          ref="samplesPanelRef"
          :enrollment-id="enrollment.id"
          :can-manage="canManage"
          @updated="onSamplesUpdated"
        />
      </section>

      <section v-else-if="tab === 'activity'">
        <EnrollmentActivityPanel :enrollment-id="enrollment.id" :label="enrollment.label" />
      </section>

      <section v-else>
        <EnrollmentSettingsForm :enrollment="enrollment" @updated="enrollment = $event" />
      </section>

      <NModal
        :show="teaching"
        preset="card"
        title="Add samples"
        class="teach-modal"
        :style="{ width: 'min(720px, calc(100vw - 32px))' }"
        @update:show="(open: boolean) => { if (!open) closeTeach(); }"
      >
        <p class="or-muted or-small" style="margin: -4px 0 16px">
          Pick what to teach, then record or upload. One kind at a time is easier.
        </p>
        <AddSamplesPanel
          v-model:file-list="fileList"
          :chrome="false"
          :enrollment-type="enrollment.type"
          :quality="enrollment.quality"
          :uploading="uploading"
          @upload="addFiles"
          @done="closeTeach"
          @open-voice-wizard="showVoiceWizard = true"
          @open-face-wizard="showFaceWizard = true"
          @open-photo-wizard="showPhotoWizard = true"
          @open-video-wizard="showVideoWizard = true"
        />
      </NModal>
      <VoiceRegistrationModal
        v-model:show="showVoiceWizard"
        :enrollment-id="enrollment.id"
        :enrollment-label="enrollment.label"
        :enrollment-type="enrollment.type"
        @completed="afterWizard('Voice samples added', $event)"
      />
      <FaceEnrollmentModal
        v-if="enrollment.type === 'person'"
        v-model:show="showFaceWizard"
        :enrollment-id="enrollment.id"
        :enrollment-label="enrollment.label"
        @completed="afterWizard('Face photos added', $event)"
      />
      <PhotoEnrollmentModal
        v-if="enrollment.type === 'pet' || enrollment.type === 'object'"
        v-model:show="showPhotoWizard"
        :enrollment-id="enrollment.id"
        :enrollment-label="enrollment.label"
        :enrollment-type="enrollment.type"
        @completed="afterWizard('Photos added', $event)"
      />
      <VideoEnrollmentModal
        v-model:show="showVideoWizard"
        :enrollment-id="enrollment.id"
        :enrollment-label="enrollment.label"
        :enrollment-type="enrollment.type"
        @completed="afterWizard('Video clip added', $event)"
      />
    </template>
  </div>
</template>

<style scoped>
.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: var(--or-space-6);
  align-items: start;
}

.setup {
  margin: 12px 0 0;
  padding-left: 1.2rem;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.setup .done {
  color: var(--or-text-3);
  text-decoration: line-through;
}

.about dl {
  margin: 12px 0 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.about dt {
  font-size: var(--or-text-micro);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--or-text-3);
}

.about dd {
  margin: 2px 0 0;
  overflow-wrap: anywhere;
}

@media (max-width: 1199px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
