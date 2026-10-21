<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import {
  NDataTable,
  NButton,
  NSelect,
  NInput,
  NTag,
  NSkeleton,
  NPagination,
  NSpace,
  NIcon,
  useMessage,
} from "naive-ui";
import type { DataTableColumns, SelectOption } from "naive-ui";
import { RefreshOutline, DocumentTextOutline, EyeOutline } from "@vicons/ionicons5";
import { api, loadFailureMessage } from "@/api/client";
import type { RecognitionLogListOut, RecognitionLogOut } from "@/types/api";
import AppPageHeader from "@/components/AppPageHeader.vue";
import EmptyState from "@/components/EmptyState.vue";
import LogDetailModal from "@/components/LogDetailModal.vue";
import { formatLogEvent, formatLogMedia } from "@/utils/logEvent";

const message = useMessage();
const loading = ref(true);
const loadError = ref<string | null>(null);
const rows = ref<RecognitionLogOut[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(50);

const eventFilter = ref<string | null>(null);
const modalityFilter = ref<string | null>(null);
const labelFilter = ref("");
const selectedLog = ref<RecognitionLogOut | null>(null);
const showDetail = ref(false);

const eventOptions: SelectOption[] = [
  { label: "All events", value: "" },
  { label: "Match", value: "recognition.match" },
  { label: "Unknown", value: "recognition.unknown" },
  { label: "No match", value: "recognition.no_match" },
  { label: "Speech check", value: "recognition.gate" },
  { label: "Speech check rejected", value: "recognition.gate_reject" },
  { label: "Transcript", value: "wyoming.transcript" },
  { label: "Blocked", value: "wyoming.blocked" },
  { label: "Nothing heard", value: "wyoming.empty" },
  { label: "Created", value: "enrollment.created" },
  { label: "Samples added", value: "enrollment.samples_added" },
];

const modalityOptions: SelectOption[] = [
  { label: "All media", value: "" },
  { label: "Voice", value: "audio" },
  { label: "Photo", value: "image" },
  { label: "Video", value: "video" },
  { label: "Library", value: "enrollment" },
];

function eventTagType(event: string) {
  if (event === "recognition.match") return "success";
  if (event === "recognition.unknown") return "warning";
  if (event.startsWith("enrollment.")) return "info";
  if (event === "recognition.gate_reject") return "error";
  if (event === "wyoming.transcript") return "success";
  if (event === "wyoming.blocked") return "warning";
  if (event === "wyoming.empty") return "default";
  if (event === "recognition.no_match") return "default";
  return "default";
}

function formatEvent(event: string) {
  return formatLogEvent(event);
}

function formatConfidence(row: RecognitionLogOut) {
  if (row.event.startsWith("enrollment.")) return "n/a";
  if (row.confidence == null) return "—";
  return `${Math.round(row.confidence * 100)}%`;
}

function openDetail(row: RecognitionLogOut) {
  selectedLog.value = row;
  showDetail.value = true;
}

function formatActor(row: RecognitionLogOut) {
  if (!row.actor_name && !row.actor_type) return "—";
  const kind =
    row.actor_type === "api_key" ? "key" : row.actor_type === "user" ? "user" : row.actor_type ?? "";
  return row.actor_name ? `${row.actor_name}${kind ? ` (${kind})` : ""}` : kind || "—";
}

const columns: DataTableColumns<RecognitionLogOut> = [
  {
    title: "Time",
    key: "created_at",
    width: 168,
    render(row) {
      return new Date(row.created_at).toLocaleString();
    },
  },
  {
    title: "Event",
    key: "event",
    width: 168,
    render(row) {
      return h(NSpace, { size: 4, align: "center" }, () => [
        h(
          NTag,
          { size: "small", type: eventTagType(row.event), bordered: false, round: true },
          () => formatEvent(row.event),
        ),
        row.dry_run
          ? h(NTag, { size: "small", type: "default", bordered: false, round: true }, () => "Practice")
          : null,
      ]);
    },
  },
  {
    title: "Label",
    key: "label",
    minWidth: 120,
    ellipsis: { tooltip: true },
    render(row) {
      return row.label ?? "—";
    },
  },
  {
    title: "Details",
    key: "summary",
    minWidth: 160,
    ellipsis: { tooltip: true },
    render(row) {
      return row.summary ?? row.reason ?? "—";
    },
  },
  {
    title: "Score",
    key: "confidence",
    width: 80,
    render(row) {
      const text = formatConfidence(row);
      if (text === "n/a") {
        return h("span", { class: "muted-cell" }, text);
      }
      return text;
    },
  },
  {
    title: "Media",
    key: "modality",
    width: 100,
    render(row) {
      return formatLogMedia(row.modality);
    },
  },
  {
    title: "Actor",
    key: "actor_name",
    minWidth: 140,
    ellipsis: { tooltip: true },
    render(row) {
      return formatActor(row);
    },
  },
  {
    title: "",
    key: "actions",
    width: 52,
    fixed: "right",
    render(row) {
      return h(
        NButton,
        {
          quaternary: true,
          size: "small",
          title: "View details",
          onClick: (e: Event) => {
            e.stopPropagation();
            openDetail(row);
          },
        },
        {
          icon: () => h(NIcon, null, () => h(EyeOutline)),
        },
      );
    },
  },
];

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));

async function load() {
  loading.value = true;
  try {
    const params = new URLSearchParams({
      limit: String(pageSize.value),
      offset: String((page.value - 1) * pageSize.value),
    });
    if (eventFilter.value) params.set("event", eventFilter.value);
    if (modalityFilter.value) params.set("modality", modalityFilter.value);
    const label = labelFilter.value.trim();
    if (label) params.set("label", label);

    const res = await api<RecognitionLogListOut>(`/v1/admin/logs?${params}`);
    rows.value = res.items;
    total.value = res.total;
    loadError.value = null;
  } catch (e) {
    loadError.value = loadFailureMessage(e, "Failed to load logs");
    message.error(loadError.value);
  } finally {
    loading.value = false;
  }
}

function applyFilters() {
  page.value = 1;
  void load();
}

function onPageChange(p: number) {
  page.value = p;
  void load();
}

function onPageSizeChange(size: number) {
  pageSize.value = size;
  page.value = 1;
  void load();
}

onMounted(load);
</script>

<template>
  <div>
    <AppPageHeader
      title="Activity"
      description="What this server recognized, enrolled, or rejected. Media is not stored here."
    >
      <template #action>
        <NButton quaternary :loading="loading" @click="load">
          <template #icon>
            <NIcon><RefreshOutline /></NIcon>
          </template>
          Refresh
        </NButton>
      </template>
      <template #extra>
        <NSpace wrap :size="12" align="center">
        <NSelect
          v-model:value="eventFilter"
          :options="eventOptions"
          clearable
          placeholder="Event"
          style="width: 160px"
          @update:value="applyFilters"
        />
        <NSelect
          v-model:value="modalityFilter"
          :options="modalityOptions"
          clearable
          placeholder="Media"
          style="width: 160px"
          @update:value="applyFilters"
        />
        <NInput
          v-model:value="labelFilter"
          placeholder="Filter by label"
          clearable
          style="width: 200px"
          @keyup.enter="applyFilters"
          @clear="applyFilters"
        />
        <NButton secondary @click="applyFilters">Apply</NButton>
        </NSpace>
      </template>
    </AppPageHeader>

    <NSpace vertical :size="16">
      <NSkeleton v-if="loading && !rows.length" text :repeat="6" />
      <EmptyState
        v-else-if="!loading && loadError"
        title="Couldn't load activity"
        :description="loadError"
        action-label="Retry"
        @action="load"
      />
      <EmptyState
        v-else-if="!loading && !rows.length"
        title="No activity yet"
        description="Add samples or try a match. Events show up here."
      >
        <template #icon>
          <NIcon :size="48" depth="3"><DocumentTextOutline /></NIcon>
        </template>
      </EmptyState>
      <template v-else>
        <div class="or-list-cards">
          <button
            v-for="row in rows"
            :key="row.id"
            type="button"
            class="or-list-card"
            @click="openDetail(row)"
          >
            <span class="or-list-card__title">{{ row.label || formatEvent(row.event) }}</span>
            <span class="or-list-card__meta">
              <span>{{ formatEvent(row.event) }}</span>
              <span>{{ formatLogMedia(row.modality) }}</span>
              <span>{{ formatConfidence(row) }}</span>
            </span>
          </button>
        </div>
        <div class="or-table-wrap or-table-desktop">
        <NDataTable
          :columns="columns"
          :data="rows"
          :loading="loading"
          :bordered="false"
          size="medium"
          :row-key="(row: RecognitionLogOut) => row.id"
          :row-props="(row: RecognitionLogOut) => ({
            style: 'cursor: pointer',
            onClick: () => openDetail(row),
          })"
        />
        </div>
        <LogDetailModal v-model:show="showDetail" :log="selectedLog" />
        <div class="logs-footer">
          <span class="logs-total">{{ total }} event{{ total === 1 ? "" : "s" }}</span>
          <NPagination
            v-if="total > pageSize"
            :page="page"
            :page-count="pageCount"
            :page-size="pageSize"
            show-size-picker
            :page-sizes="[25, 50, 100]"
            @update:page="onPageChange"
            @update:page-size="onPageSizeChange"
          />
        </div>
      </template>
    </NSpace>
  </div>
</template>

<style scoped>
.logs-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
}

.logs-total {
  font-size: 0.875rem;
  color: var(--n-text-color-3);
}

:deep(.muted-cell) {
  color: var(--n-text-color-3);
  font-size: 0.8125rem;
}
</style>
