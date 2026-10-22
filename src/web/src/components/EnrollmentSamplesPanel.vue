<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from "vue";
import {
  NDataTable,
  NButton,
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
import { TrashOutline, RefreshOutline } from "@vicons/ionicons5";
import { api } from "@/api/client";
import type { EnrollmentOut, SampleOut } from "@/types/api";
import { ApiError } from "@/api/client";
import {
  formatFitPct,
  sampleFlagLabels,
  sampleSourceLabels,
} from "@/utils/sampleLabels";
import SampleDetailModal from "@/components/SampleDetailModal.vue";
import FilterBar from "@/components/kit/FilterBar.vue";
import Chip from "@/components/kit/Chip.vue";
import TimeAgo from "@/components/kit/TimeAgo.vue";
import EmptyState from "@/components/EmptyState.vue";

const props = withDefaults(
  defineProps<{
    enrollmentId: string;
    canManage?: boolean;
  }>(),
  { canManage: true },
);

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
  ...(props.canManage ? [{ type: "selection" as const }] : []),
  {
    title: "Source",
    key: "source_label",
    minWidth: 200,
    ellipsis: { tooltip: true },
    sorter: (a, b) => a.source_label.localeCompare(b.source_label),
    render(row) {
      const flag = row.flags[0];
      const flagMeta = flag ? sampleFlagLabels[flag] : null;
      return h("div", { class: "source-cell" }, [
        h("span", { class: "source-detail" }, row.source_label),
        h("div", { class: "source-meta" }, [
          h(Chip, null, { default: () => sampleSourceLabels[row.source] ?? row.source }),
          flagMeta
            ? h(
                Chip,
                { tone: flagMeta.type === "error" ? "error" : flagMeta.type === "warning" ? "warning" : "default" },
                { default: () => flagMeta.label },
              )
            : null,
        ]),
      ]);
    },
  },
  {
    title: "Type",
    key: "modality",
    width: 100,
    sorter: (a, b) => a.modality.localeCompare(b.modality),
    render(row) {
      const tone = row.modality === "audio" ? "audio" : row.modality === "image" ? "image" : "default";
      return h(Chip, { tone }, { default: () => modalityLabel(row.modality) });
    },
  },
  {
    title: "Fit",
    key: "centroid_similarity",
    width: 88,
    sorter: (a, b) => (a.centroid_similarity ?? -1) - (b.centroid_similarity ?? -1),
    render(row) {
      const pct = formatFitPct(row.centroid_similarity);
      const low = row.centroid_similarity != null && row.centroid_similarity < 0.5;
      return h("span", { class: low ? "fit-low" : "fit-ok" }, pct);
    },
  },
  {
    title: "Added",
    key: "created_at",
    width: 120,
    sorter: (a, b) => a.created_at.localeCompare(b.created_at),
    render(row) {
      return h(TimeAgo, { value: row.created_at });
    },
  },
  ...(props.canManage
    ? [
  {
    title: "",
    key: "actions",
    width: 80,
    className: "actions-cell",
    render(row: SampleOut) {
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
    ]
    : []),
]);

onMounted(load);

watch(
  () => props.enrollmentId,
  () => {
    void load();
  },
);

defineExpose({ reload: load });
</script>

<template>
  <div class="samples-panel">
    <div class="panel-header">
      <div>
        <h2 class="or-heading">Samples</h2>
        <p class="or-muted or-small" style="margin-top: 4px">
          What this profile already knows. Open a row for details.
        </p>
      </div>
      <NButton size="small" quaternary :loading="loading" @click="load">
        <template #icon>
          <NIcon><RefreshOutline /></NIcon>
        </template>
        Refresh
      </NButton>
    </div>

    <FilterBar :active="hasActiveFilters" @clear="clearFilters">
      <NInput
        v-model:value="searchQuery"
        clearable
        size="small"
        placeholder="Search samples"
        style="width: min(100%, 220px)"
      />
      <NSelect
        v-model:value="filterModality"
        :options="modalityOptions"
        placeholder="Type"
        clearable
        size="small"
        style="width: 132px"
      />
      <NSelect
        v-model:value="filterSource"
        :options="sourceOptions"
        placeholder="Source"
        clearable
        size="small"
        style="width: 148px"
      />
      <NSelect
        v-model:value="filterFlag"
        :options="flagOptions"
        placeholder="Flags"
        clearable
        size="small"
        style="width: 160px"
      />
    </FilterBar>

    <div v-if="canManage && selectionCount > 0" class="bulk-bar">
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

    <EmptyState
      v-if="!loading && samples.length === 0"
      title="No samples yet"
      description="Add voice, photos, or a clip. They will show up here."
    />
    <p v-else-if="!loading && filteredSamples.length === 0" class="or-muted" style="text-align: center">
      Nothing matches.
    </p>
    <div v-else class="or-table-wrap">
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
      />
    </div>

    <SampleDetailModal
      v-model:show="showDetailModal"
      :sample="detailSample"
      :deleting="detailSample != null && deletingId === detailSample.id"
      :can-delete="canManage"
      @delete="deleteFromDetail"
    />
  </div>
</template>

<style scoped>
.samples-panel {
  display: flex;
  flex-direction: column;
  gap: var(--or-space-4);
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.bulk-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px 14px;
  border-radius: var(--or-radius-md);
  background: color-mix(in oklab, var(--or-danger, #d03050) 10%, var(--or-surface));
  border: 1px solid color-mix(in oklab, var(--or-danger, #d03050) 28%, var(--or-line));
}

.bulk-count {
  font-size: var(--or-text-small);
  font-weight: 500;
}

:deep(.source-cell) {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 2px 0;
  min-width: 0;
}

:deep(.source-detail) {
  font-weight: 500;
  line-height: 1.35;
  color: var(--or-text-1);
}

:deep(.source-meta) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.fit-low {
  color: var(--or-warning, var(--n-warning-color));
  font-weight: 500;
}

.fit-ok {
  color: var(--or-text-2);
}

:deep(.actions-cell) {
  width: 80px;
}

:deep(.sample-row-actions) {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}
</style>
