<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import {
  NDataTable,
  NButton,
  NSelect,
  NInput,
  NTag,
  NSpace,
  NIcon,
  useMessage,
} from "naive-ui";
import type { DataTableColumns, SelectOption } from "naive-ui";
import { RefreshOutline, DocumentTextOutline, EyeOutline } from "@vicons/ionicons5";
import { api, loadFailureMessage } from "@/api/client";
import type { RecognitionLogListOut, RecognitionLogOut } from "@/types/api";
import PageHeader from "@/components/kit/PageHeader.vue";
import FilterBar from "@/components/kit/FilterBar.vue";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import EmptyState from "@/components/EmptyState.vue";
import LogDetailModal from "@/components/LogDetailModal.vue";
import TimeAgo from "@/components/kit/TimeAgo.vue";
import { formatLogMedia } from "@/utils/logEvent";
import {
  collapseActivityRows,
  groupBlurb,
  groupEvent,
  groupLabel,
  newestLog,
  type ActivityGroup,
} from "@/utils/activityStory";
import { useEventStream } from "@/composables/useEventStream";

const PAGE_SIZE = 40;

const message = useMessage();
const loading = ref(true);
const loadingMore = ref(false);
const loadError = ref<string | null>(null);
const rows = ref<RecognitionLogOut[]>([]);
const total = ref(0);

const eventFilter = ref<string | null>(null);
const modalityFilter = ref<string | null>(null);
const labelFilter = ref("");
const selectedLogs = ref<RecognitionLogOut[] | null>(null);
const showDetail = ref(false);
const groups = computed(() => collapseActivityRows(rows.value));

const hasMore = computed(() => rows.value.length < total.value);
const filtersActive = computed(
  () => !!eventFilter.value || !!modalityFilter.value || !!labelFilter.value.trim(),
);

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

function formatConfidence(row: RecognitionLogOut) {
  if (row.event.startsWith("enrollment.")) return "n/a";
  if (row.confidence == null) return "—";
  return `${Math.round(row.confidence * 100)}%`;
}

function openDetail(group: ActivityGroup) {
  selectedLogs.value = group.logs;
  showDetail.value = true;
}

function formatActor(row: RecognitionLogOut) {
  if (!row.actor_name && !row.actor_type) return "—";
  const kind =
    row.actor_type === "api_key" ? "key" : row.actor_type === "user" ? "user" : row.actor_type ?? "";
  return row.actor_name ? `${row.actor_name}${kind ? ` (${kind})` : ""}` : kind || "—";
}

function queryParams(offset: number) {
  const params = new URLSearchParams({
    limit: String(PAGE_SIZE),
    offset: String(offset),
  });
  if (eventFilter.value) params.set("event", eventFilter.value);
  if (modalityFilter.value) params.set("modality", modalityFilter.value);
  const label = labelFilter.value.trim();
  if (label) params.set("label", label);
  return params;
}

const columns: DataTableColumns<ActivityGroup> = [
  {
    title: "Time",
    key: "created_at",
    width: 120,
    render(row) {
      const latest = newestLog(row.logs);
      return latest ? h(TimeAgo, { value: latest.created_at }) : "—";
    },
  },
  {
    title: "Event",
    key: "event",
    width: 220,
    render(row) {
      const event = groupEvent(row.logs);
      const latest = newestLog(row.logs);
      return h(NSpace, { size: 6, align: "center", wrap: false }, () => [
        h(
          NTag,
          { size: "small", type: eventTagType(event.event), bordered: false, round: true },
          () => event.label,
        ),
        row.logs.length > 1
          ? h(NTag, { size: "small", bordered: false, round: true }, () => String(row.logs.length))
          : null,
        latest?.dry_run
          ? h(NTag, { size: "small", type: "default", bordered: false, round: true }, () => "Practice")
          : null,
      ]);
    },
  },
  {
    title: "Label",
    key: "label",
    minWidth: 140,
    ellipsis: { tooltip: true },
    render(row) {
      return groupLabel(row.logs);
    },
  },
  {
    title: "Details",
    key: "summary",
    minWidth: 180,
    ellipsis: { tooltip: true },
    render(row) {
      return groupBlurb(row.logs);
    },
  },
  {
    title: "Score",
    key: "confidence",
    width: 72,
    render(row) {
      const latest = newestLog(row.logs);
      const text = latest ? formatConfidence(latest) : "—";
      if (text === "n/a" || text === "—") {
        return h("span", { class: "muted-cell" }, text);
      }
      return text;
    },
  },
  {
    title: "Media",
    key: "modality",
    width: 88,
    render(row) {
      return formatLogMedia(newestLog(row.logs)?.modality);
    },
  },
  {
    title: "Actor",
    key: "actor_name",
    minWidth: 140,
    ellipsis: { tooltip: true },
    render(row) {
      const latest = newestLog(row.logs);
      return latest ? formatActor(latest) : "—";
    },
  },
  {
    title: "",
    key: "actions",
    width: 48,
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
          icon: () => h(NIcon, { size: 18 }, () => h(EyeOutline)),
        },
      );
    },
  },
];

async function fetchPage(append: boolean) {
  if (append) {
    if (loadingMore.value || !hasMore.value) return;
    loadingMore.value = true;
  } else {
    loading.value = true;
  }
  try {
    const offset = append ? rows.value.length : 0;
    const res = await api<RecognitionLogListOut>(`/v1/admin/logs?${queryParams(offset)}`);
    if (append) {
      const seen = new Set(rows.value.map((row) => row.id));
      rows.value = [...rows.value, ...res.items.filter((row) => !seen.has(row.id))];
    } else {
      rows.value = res.items;
    }
    total.value = res.total;
    loadError.value = null;
  } catch (e) {
    loadError.value = loadFailureMessage(e, "Failed to load logs");
    if (!append) message.error(loadError.value);
  } finally {
    loading.value = false;
    loadingMore.value = false;
  }
}

function load() {
  return fetchPage(false);
}

function loadMore() {
  return fetchPage(true);
}

function onTableScroll(e: Event) {
  const el = e.target as HTMLElement | null;
  if (!el || loadingMore.value || !hasMore.value) return;
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 120) {
    void loadMore();
  }
}

function applyFilters() {
  void load();
}

function clearFilters() {
  eventFilter.value = null;
  modalityFilter.value = null;
  labelFilter.value = "";
  applyFilters();
}

function rowMatchesFilters(row: RecognitionLogOut) {
  if (eventFilter.value && row.event !== eventFilter.value) return false;
  if (modalityFilter.value && row.modality !== modalityFilter.value) return false;
  const label = labelFilter.value.trim().toLowerCase();
  if (label && !(row.label ?? "").toLowerCase().includes(label)) return false;
  return true;
}

useEventStream((event) => {
  const log = event.log;
  if (!log || event.type !== "recognition.log") return;
  if (!rowMatchesFilters(log)) return;
  if (rows.value.some((row) => row.id === log.id)) return;
  rows.value = [log, ...rows.value];
  total.value += 1;
});

onMounted(load);
</script>

<template>
  <div class="or-page logs-page">
    <PageHeader
      title="Activity"
      description="What this server recognized, enrolled, or rejected. Media is not stored here."
    >
      <template #meta>
        <span v-if="rows.length" class="or-footer-count">
          {{ rows.length }}{{ hasMore ? ` of ${total}` : "" }}
          event{{ total === 1 ? "" : "s" }}
          <template v-if="loadingMore"> · loading more</template>
        </span>
      </template>
      <template #action>
        <NButton quaternary :loading="loading && !loadingMore" @click="load">
          <template #icon>
            <NIcon><RefreshOutline /></NIcon>
          </template>
          Refresh
        </NButton>
      </template>
      <template #extra>
        <FilterBar :active="filtersActive" @clear="clearFilters">
          <NSelect
            v-model:value="eventFilter"
            :options="eventOptions"
            clearable
            size="small"
            placeholder="Event"
            style="width: 148px"
            @update:value="applyFilters"
          />
          <NSelect
            v-model:value="modalityFilter"
            :options="modalityOptions"
            clearable
            size="small"
            placeholder="Media"
            style="width: 132px"
            @update:value="applyFilters"
          />
          <NInput
            v-model:value="labelFilter"
            placeholder="Filter by label"
            clearable
            size="small"
            style="width: 180px"
            @keyup.enter="applyFilters"
            @clear="applyFilters"
          />
        </FilterBar>
      </template>
    </PageHeader>

    <ContentSkeleton v-if="loading && !rows.length" variant="table" />
    <EmptyState
      v-else-if="!loading && loadError && !rows.length"
      title="Couldn't load activity"
      :description="loadError"
      action-label="Retry"
      @action="load"
    />
    <EmptyState
      v-else-if="!loading && !rows.length"
      title="No activity yet"
      description="Add samples or recognize something. Events show up here."
    >
      <template #icon>
        <NIcon :size="48" depth="3"><DocumentTextOutline /></NIcon>
      </template>
    </EmptyState>
    <div v-else class="or-table-wrap logs-table">
      <NDataTable
        :columns="columns"
        :data="groups"
        :loading="loading && !loadingMore"
        :bordered="false"
        flex-height
        virtual-scroll
        :header-height="44"
        :min-row-height="48"
        :scroll-x="980"
        size="medium"
        :row-key="(row: ActivityGroup) => row.id"
        :row-props="(row: ActivityGroup) => ({
          style: 'cursor: pointer',
          onClick: () => openDetail(row),
        })"
        @scroll="onTableScroll"
      />
    </div>
    <LogDetailModal v-model:show="showDetail" :logs="selectedLogs" />
  </div>
</template>

<style scoped>
.logs-page {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  gap: var(--or-space-4);
}

.logs-table {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.logs-table :deep(.n-data-table) {
  flex: 1;
  height: 100%;
}

:deep(.muted-cell) {
  color: var(--n-text-color-3);
}
</style>
