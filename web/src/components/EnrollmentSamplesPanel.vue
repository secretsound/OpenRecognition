<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from "vue";
import {
  NCard,
  NDataTable,
  NButton,
  NTag,
  NPopconfirm,
  NSpace,
  NIcon,
  NInput,
  NSelect,
  useMessage,
  type DataTableColumns,
  type DataTableRowKey,
  type PaginationProps,
  type SelectOption,
} from "naive-ui";
import { TrashOutline, RefreshOutline, SearchOutline } from "@vicons/ionicons5";
import { api } from "@/api/client";
import type { EnrollmentOut, SampleOut } from "@/types/api";
import { ApiError } from "@/api/client";
import {
  formatFitPct,
  sampleFlagLabels,
  sampleSourceLabels,
} from "@/utils/sampleLabels";
import SampleDetailModal from "@/components/SampleDetailModal.vue";

const props = defineProps<{
  enrollmentId: string;
}>();

const emit = defineEmits<{
  updated: [enrollment: EnrollmentOut];
}>();

const message = useMessage();
const loading = ref(true);
const bulkDeleting = ref(false);
const deletingId = ref<string | null>(null);
const samples = ref<SampleOut[]>([]);

const searchQuery = ref("");
const filterModality = ref<string | null>(null);
const filterSource = ref<string | null>(null);
const filterFlag = ref<string | null>(null);

const checkedRowKeys = ref<DataTableRowKey[]>([]);
const page = ref(1);
const pageSize = ref(10);
const showDetailModal = ref(false);
const detailSample = ref<SampleOut | null>(null);

const modalityOptions = computed<SelectOption[]>(() => {
  const mods = [...new Set(samples.value.map((s) => s.modality))].sort();
  return mods.map((m) => ({ label: modalityLabel(m), value: m }));
});

const sourceOptions = computed<SelectOption[]>(() => {
  const sources = [...new Set(samples.value.map((s) => s.source))].sort();
  return sources.map((s) => ({
    label: sampleSourceLabels[s] ?? s,
    value: s,
  }));
});

const flagOptions: SelectOption[] = [
  { label: "Old embedding model", value: "outdated_model" },
  { label: "Poor match to profile", value: "poor_fit" },
  { label: "Low match to profile", value: "low_fit" },
  { label: "Source not recorded", value: "unknown_source" },
];

const hasActiveFilters = computed(
  () =>
    !!searchQuery.value.trim() ||
    !!filterModality.value ||
    !!filterSource.value ||
    !!filterFlag.value,
);

const filteredSamples = computed(() => {
  let list = samples.value;

  if (filterModality.value) {
    list = list.filter((s) => s.modality === filterModality.value);
  }
  if (filterSource.value) {
    list = list.filter((s) => s.source === filterSource.value);
  }
  if (filterFlag.value) {
    list = list.filter((s) => s.flags.includes(filterFlag.value!));
  }

  const q = searchQuery.value.trim().toLowerCase();
  if (q) {
    list = list.filter((s) => {
      const haystack = [
        s.source_label,
        s.original_filename ?? "",
        s.model_version,
        s.modality,
        modalityLabel(s.modality),
        sampleSourceLabels[s.source] ?? s.source,
        s.phrase_text ?? "",
        ...s.flags.map((f) => sampleFlagLabels[f]?.label ?? f),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }

  return list;
});

const selectionCount = computed(() => checkedRowKeys.value.length);

const pagination = computed(() => ({
  page: page.value,
  pageSize: pageSize.value,
  itemCount: filteredSamples.value.length,
  showSizePicker: true,
  pageSizes: [10, 25, 50, 100],
  prefix: (info: Parameters<NonNullable<PaginationProps["prefix"]>>[0]) =>
    `${info.itemCount ?? 0} sample${info.itemCount === 1 ? "" : "s"}`,
}));

watch([searchQuery, filterModality, filterSource, filterFlag], () => {
  page.value = 1;
});

watch(filteredSamples, () => {
  const visible = new Set(filteredSamples.value.map((s) => s.id));
  checkedRowKeys.value = checkedRowKeys.value.filter((k) => visible.has(String(k)));
});

function clearFilters() {
  searchQuery.value = "";
  filterModality.value = null;
  filterSource.value = null;
  filterFlag.value = null;
}

async function load() {
  loading.value = true;
  try {
    samples.value = await api<SampleOut[]>(`/v1/enrollments/${props.enrollmentId}/samples`);
    checkedRowKeys.value = [];
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load samples");
  } finally {
    loading.value = false;
  }
}

async function refreshEnrollment() {
  const en = await api<EnrollmentOut>(`/v1/enrollments/${props.enrollmentId}`);
  emit("updated", en);
}

async function removeSampleIds(ids: string[]) {
  let ok = 0;
  let fail = 0;
  for (const id of ids) {
    try {
      await api(`/v1/enrollments/${props.enrollmentId}/samples/${id}`, {
        method: "DELETE",
      });
      ok++;
    } catch {
      fail++;
    }
  }
  await load();
  await refreshEnrollment();
  if (fail > 0) {
    message.warning(`Removed ${ok}; ${fail} could not be deleted`);
  } else if (ok > 0) {
    message.success(`Removed ${ok} sample${ok === 1 ? "" : "s"}`);
  }
  return { ok, fail };
}

async function removeSample(sample: SampleOut) {
  deletingId.value = sample.id;
  try {
    await removeSampleIds([sample.id]);
  } finally {
    deletingId.value = null;
  }
}

async function removeSelected() {
  const ids = checkedRowKeys.value.map(String);
  if (ids.length === 0) return;
  bulkDeleting.value = true;
  try {
    await removeSampleIds(ids);
    checkedRowKeys.value = [];
  } finally {
    bulkDeleting.value = false;
  }
}

function modalityLabel(mod: string): string {
  if (mod === "audio") return "Voice";
  if (mod === "image") return "Face";
  return mod;
}

function isRowActionClick(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return !!(
    target.closest(".n-checkbox") ||
    target.closest(".sample-row-actions") ||
    target.closest("button")
  );
}

function openSampleDetail(row: SampleOut) {
  detailSample.value = row;
  showDetailModal.value = true;
}

function rowProps(row: SampleOut) {
  return {
    style: "cursor: pointer",
    onClick: (e: MouseEvent) => {
      if (isRowActionClick(e.target)) return;
      openSampleDetail(row);
    },
  };
}

async function deleteFromDetail() {
  if (!detailSample.value) return;
  await removeSample(detailSample.value);
  showDetailModal.value = false;
  detailSample.value = null;
}

const columns = computed<DataTableColumns<SampleOut>>(() => [
  { type: "selection" },
  {
    title: "Source",
    key: "source_label",
    minWidth: 200,
    ellipsis: { tooltip: true },
    sorter: (a, b) => a.source_label.localeCompare(b.source_label),
    render(row) {
      return h("div", { class: "source-cell" }, [
        h(
          NTag,
          { size: "tiny", round: true, bordered: false, type: "info" },
          () => sampleSourceLabels[row.source] ?? row.source,
        ),
        h("span", { class: "source-detail" }, row.source_label),
        row.original_filename
          ? h("span", { class: "source-file" }, row.original_filename)
          : null,
        ...row.flags.map((f) => {
          const meta = sampleFlagLabels[f];
          return h(
            NTag,
            { size: "tiny", bordered: false, type: meta?.type ?? "default" },
            () => meta?.label ?? f,
          );
        }),
      ]);
    },
  },
  {
    title: "Type",
    key: "modality",
    width: 88,
    sorter: (a, b) => a.modality.localeCompare(b.modality),
    render(row) {
      return h(NTag, { size: "small", bordered: false }, () => modalityLabel(row.modality));
    },
  },
  {
    title: "Fit",
    key: "centroid_similarity",
    width: 80,
    sorter: (a, b) => (a.centroid_similarity ?? -1) - (b.centroid_similarity ?? -1),
    render(row) {
      const pct = formatFitPct(row.centroid_similarity);
      const low = row.centroid_similarity != null && row.centroid_similarity < 0.5;
      return h("span", { class: low ? "fit-low" : "fit-ok" }, pct);
    },
  },
  {
    title: "",
    key: "actions",
    width: 56,
    render(row) {
      return h(
        "div",
        {
          class: "sample-row-actions",
          onClick: (e: Event) => e.stopPropagation(),
        },
        [
          h(
            NPopconfirm,
            { onPositiveClick: () => removeSample(row) },
            {
              trigger: () =>
                h(
                  NButton,
                  {
                    size: "small",
                    type: "error",
                    quaternary: true,
                    loading: deletingId.value === row.id,
                  },
                  { icon: () => h(NIcon, null, () => h(TrashOutline)) },
                ),
              default: () => "Remove this sample?",
            },
          ),
        ],
      );
    },
  },
]);

onMounted(load);

defineExpose({ reload: load });
</script>

<template>
  <NCard :bordered="false" class="samples-panel">
    <template #header>
      <div class="panel-header">
        <div>
          <h2 class="panel-title">Samples</h2>
          <p class="panel-subtitle">
            Open a sample to see details, or search to find one.
          </p>
        </div>
        <NButton size="small" quaternary :loading="loading" @click="load">
          <template #icon>
            <NIcon><RefreshOutline /></NIcon>
          </template>
          Refresh
        </NButton>
      </div>
    </template>

    <div class="toolbar">
      <NInput
        v-model:value="searchQuery"
        clearable
        placeholder="Search samples"
        class="toolbar-search"
      >
        <template #prefix>
          <NIcon :depth="3"><SearchOutline /></NIcon>
        </template>
      </NInput>
      <NSelect
        v-model:value="filterModality"
        :options="modalityOptions"
        placeholder="Type"
        clearable
        class="toolbar-filter"
      />
      <NSelect
        v-model:value="filterSource"
        :options="sourceOptions"
        placeholder="Source"
        clearable
        class="toolbar-filter"
      />
      <NSelect
        v-model:value="filterFlag"
        :options="flagOptions"
        placeholder="Flags"
        clearable
        class="toolbar-filter"
      />
      <NButton v-if="hasActiveFilters" quaternary size="small" @click="clearFilters">
        Clear filters
      </NButton>
    </div>

    <div v-if="selectionCount > 0" class="bulk-bar">
      <span class="bulk-count">{{ selectionCount }} selected</span>
      <NSpace :size="8">
        <NButton size="small" quaternary @click="checkedRowKeys = []">Clear selection</NButton>
        <NPopconfirm @positive-click="removeSelected">
          <template #trigger>
            <NButton size="small" type="error" :loading="bulkDeleting">
              <template #icon>
                <NIcon><TrashOutline /></NIcon>
              </template>
              Delete selected
            </NButton>
          </template>
          Delete {{ selectionCount }} sample{{ selectionCount === 1 ? "" : "s" }}? This cannot be undone.
        </NPopconfirm>
      </NSpace>
    </div>

    <NDataTable
      v-model:checked-row-keys="checkedRowKeys"
      v-model:page="page"
      v-model:page-size="pageSize"
      :columns="columns"
      :data="filteredSamples"
      :loading="loading"
      :pagination="pagination"
      :bordered="false"
      :row-key="(row: SampleOut) => row.id"
      :row-props="rowProps"
      size="medium"
      class="samples-table"
    />

    <SampleDetailModal
      v-model:show="showDetailModal"
      :sample="detailSample"
      :deleting="detailSample != null && deletingId === detailSample.id"
      @delete="deleteFromDetail"
    />
    <p v-if="!loading && samples.length === 0" class="empty-hint">
      No samples yet. Use Training data to upload or capture samples.
    </p>
    <p v-else-if="!loading && filteredSamples.length === 0" class="empty-hint">
      No samples match your search or filters.
      <NButton text type="primary" size="small" @click="clearFilters">Clear filters</NButton>
    </p>
  </NCard>
</template>

<style scoped>
.samples-panel :deep(.n-card-header) {
  padding-bottom: 8px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  width: 100%;
}

.panel-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
}

.panel-subtitle {
  margin: 4px 0 0;
  font-size: 0.82rem;
  color: var(--n-text-color-3);
  max-width: 560px;
  line-height: 1.45;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.toolbar-search {
  flex: 1;
  min-width: 200px;
  max-width: 360px;
}

.toolbar-filter {
  width: 160px;
}

.bulk-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(208, 48, 80, 0.08);
  border: 1px solid rgba(208, 48, 80, 0.25);
}

.bulk-count {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--n-text-color-1);
}

:deep(.source-cell) {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 2px 0;
  max-width: 100%;
}

:deep(.source-detail) {
  font-size: 0.8125rem;
  font-weight: 500;
  line-height: 1.35;
  color: var(--n-text-color-1);
  word-break: break-word;
}

:deep(.source-file) {
  font-size: 0.7rem;
  color: var(--n-text-color-3);
  font-family: ui-monospace, monospace;
  word-break: break-all;
}

.fit-low {
  color: var(--n-warning-color);
  font-weight: 500;
}

.fit-ok {
  color: var(--n-text-color-2);
}

.empty-hint {
  margin: 12px 0 0;
  font-size: 0.85rem;
  color: var(--n-text-color-3);
  text-align: center;
}

.samples-table :deep(.n-data-table-tr:hover) {
  background: color-mix(in srgb, var(--n-primary-color) 6%, transparent);
}
</style>
