<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NAlert,
  NCollapse,
  NCollapseItem,
  NDescriptions,
  NDescriptionsItem,
  NDropdown,
  NSkeleton,
  useDialog,
  useMessage,
} from "naive-ui";
import type { DropdownOption } from "naive-ui";
import { api } from "@/api/client";
import type { EnrollmentOut, QualityInfo } from "@/types/api";
import DetailHeader from "@/components/DetailHeader.vue";
import StatusPill from "@/components/StatusPill.vue";
import TypeTag from "@/components/TypeTag.vue";
import QualityBreakdown from "@/components/QualityBreakdown.vue";
import EnrollmentSamplesPanel from "@/components/EnrollmentSamplesPanel.vue";
import TrainingProgressCard from "@/components/TrainingProgressCard.vue";
import TestModalityDialog from "@/components/TestModalityDialog.vue";
import { resolveTestModalityFor, type TestModality } from "@/utils/testModality";
import { ApiError } from "@/api/client";
import { useBreadcrumbTail } from "@/composables/useBreadcrumbTail";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const dialog = useDialog();

const id = computed(() => route.params.id as string);
const loading = ref(true);
const enrollment = ref<EnrollmentOut | null>(null);
const evaluating = ref(false);
const deleting = ref(false);
const samplesPanelRef = ref<InstanceType<typeof EnrollmentSamplesPanel> | null>(null);
const showTestChooser = ref(false);

const testedKey = computed(() => `or-tested-${id.value}`);
const tested = ref(false);

useBreadcrumbTail(computed(() => enrollment.value?.label));

async function load() {
  loading.value = true;
  try {
    enrollment.value = await api<EnrollmentOut>(`/v1/enrollments/${id.value}`);
    tested.value = sessionStorage.getItem(testedKey.value) === "1";
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load");
    router.push("/enrollments");
  } finally {
    loading.value = false;
  }
}

async function toggleEnabled(v: boolean) {
  if (!enrollment.value) return;
  try {
    enrollment.value = await api<EnrollmentOut>(`/v1/enrollments/${id.value}`, {
      method: "PATCH",
      json: { enabled: v },
    });
    message.success(v ? "Enrollment enabled" : "Enrollment disabled");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Update failed");
    await load();
  }
}

async function evaluate() {
  evaluating.value = true;
  try {
    const q = await api<QualityInfo>(`/v1/enrollments/${id.value}/evaluate`, {
      method: "POST",
    });
    if (enrollment.value) enrollment.value = { ...enrollment.value, quality: q };
    message.success("Quality evaluated");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Evaluate failed");
  } finally {
    evaluating.value = false;
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

async function goTestRecognition() {
  if (!enrollment.value) return;
  const choice = await resolveTestModalityFor(enrollment.value);
  if (choice === "choose") {
    showTestChooser.value = true;
    return;
  }
  pushTest(choice);
}

function pickTestModality(modality: TestModality) {
  showTestChooser.value = false;
  pushTest(modality);
}

function goTraining() {
  router.push({ name: "enrollment-training", params: { id: id.value } });
}

function goSettings() {
  router.push({ name: "enrollment-settings", params: { id: id.value } });
}

const moreOptions = computed<DropdownOption[]>(() => {
  if (!enrollment.value) return [];
  return [
    { label: "Try a match", key: "test" },
    { label: "Check quality", key: "evaluate", disabled: enrollment.value.sample_count === 0 },
    { label: enrollment.value.enabled ? "Turn off" : "Turn on", key: "toggle" },
    { type: "divider", key: "d" },
    { label: "Delete", key: "delete" },
  ];
});

async function onMore(key: string) {
  if (key === "test") await goTestRecognition();
  else if (key === "evaluate") await evaluate();
  else if (key === "toggle" && enrollment.value) await toggleEnabled(!enrollment.value.enabled);
  else if (key === "delete") {
    dialog.warning({
      title: "Delete this enrollment?",
      content: "Samples and the name are removed. This cannot be undone.",
      positiveText: "Delete",
      negativeText: "Cancel",
      onPositiveClick: () => remove(),
    });
  }
}

function onEnrollmentSamplesUpdated(updated: EnrollmentOut) {
  enrollment.value = updated;
}

async function remove() {
  deleting.value = true;
  try {
    await api(`/v1/enrollments/${id.value}`, { method: "DELETE" });
    message.success("Enrollment deleted");
    router.push("/enrollments");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Delete failed");
  } finally {
    deleting.value = false;
  }
}

watch(
  () => route.query.train,
  (v) => {
    if (v === "1") goTraining();
  },
);

onMounted(async () => {
  await load();
  if (route.query.train === "1") {
    goTraining();
    router.replace({ query: { ...route.query, train: undefined } });
  }
});
</script>

<template>
  <div class="enrollment-detail">
    <NSkeleton v-if="loading" text :repeat="6" />

    <template v-else-if="enrollment">
      <DetailHeader :title="enrollment.label" description="Samples teach this server who or what to recognize.">
        <template #meta>
          <TypeTag :type="enrollment.type" />
          <StatusPill :enrollment="enrollment" />
          <span class="detail-meta">{{ enrollment.sample_count }} samples</span>
        </template>
        <template #action>
          <NButton type="primary" @click="goTraining">Add samples</NButton>
          <NButton @click="goSettings">Settings</NButton>
          <NDropdown :options="moreOptions" @select="onMore">
            <NButton :loading="evaluating || deleting">More</NButton>
          </NDropdown>
        </template>
      </DetailHeader>

      <TrainingProgressCard
        :enrollment="enrollment"
        :tested="tested"
        @samples="goTraining"
        @evaluate="evaluate"
        @test="goTestRecognition"
      />
      <TestModalityDialog
        :show="showTestChooser"
        :label="enrollment.label"
        @update:show="showTestChooser = $event"
        @pick="pickTestModality"
      />

      <NAlert
        v-if="enrollment.duplicate_warning"
        type="warning"
        title="This may be a duplicate"
        size="small"
        :bordered="false"
      >
        {{ enrollment.duplicate_warning }}
      </NAlert>

      <section v-if="enrollment.quality" class="quality-block">
        <h2 class="section-title">Quality</h2>
        <QualityBreakdown :quality="enrollment.quality" />
      </section>

      <EnrollmentSamplesPanel
        ref="samplesPanelRef"
        :enrollment-id="enrollment.id"
        @updated="onEnrollmentSamplesUpdated"
      />

      <NCollapse>
        <NCollapseItem title="Details" name="details">
          <NDescriptions :column="1" label-placement="left" size="small">
            <NDescriptionsItem label="ID">
              <code class="mono">{{ enrollment.id }}</code>
            </NDescriptionsItem>
            <NDescriptionsItem v-if="enrollment.species_hint" label="Species">
              {{ enrollment.species_hint }}
            </NDescriptionsItem>
            <NDescriptionsItem label="Model">
              {{ enrollment.model_version ?? "—" }}
            </NDescriptionsItem>
            <NDescriptionsItem label="Created">
              {{ new Date(enrollment.created_at).toLocaleString() }}
            </NDescriptionsItem>
            <NDescriptionsItem label="Updated">
              {{ new Date(enrollment.updated_at).toLocaleString() }}
            </NDescriptionsItem>
          </NDescriptions>
        </NCollapseItem>
      </NCollapse>
    </template>
  </div>
</template>

<style scoped>
.enrollment-detail {
  display: flex;
  flex-direction: column;
  gap: var(--or-section-gap);
}

.detail-meta {
  color: var(--n-text-color-3);
  font-size: 0.8125rem;
}

.section-title {
  margin: 0 0 8px;
  font-size: 1rem;
  font-weight: 600;
}

.mono {
  font-size: 0.75rem;
  word-break: break-all;
}
</style>
