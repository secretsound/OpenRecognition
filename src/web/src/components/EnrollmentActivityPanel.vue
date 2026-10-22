<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from "vue";
import { NButton, NDataTable, NIcon, NSpace, NTag, useMessage } from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import { DocumentTextOutline, EyeOutline } from "@vicons/ionicons5";
import { api, loadFailureMessage } from "@/api/client";
import type { RecognitionLogListOut, RecognitionLogOut } from "@/types/api";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import TimeAgo from "@/components/kit/TimeAgo.vue";
import EmptyState from "@/components/EmptyState.vue";
import LogDetailModal from "@/components/LogDetailModal.vue";
import { useEventStream } from "@/composables/useEventStream";
import { formatLogMedia } from "@/utils/logEvent";
import {
  collapseActivityRows,
  groupBlurb,
  groupEvent,
  newestLog,
  type ActivityGroup,
} from "@/utils/activityStory";

const PAGE_SIZE = 40;

const props = defineProps<{
  enrollmentId: string;
  label: string;
}>();

const message = useMessage();
const loading = ref(true);
const loadingMore = ref(false);
const rows = ref<RecognitionLogOut[]>([]);
const total = ref(0);
const selectedLogs = ref<RecognitionLogOut[] | null>(null);
const showDetail = ref(false);
const groups = computed(() => collapseActivityRows(rows.value));

const hasMore = computed(() => rows.value.length < total.value);

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

function formatActor(row: RecognitionLogOut) {
  if (!row.actor_name && !row.actor_type) return "—";
  const kind =
    row.actor_type === "api_key" ? "key" : row.actor_type === "user" ? "user" : row.actor_type ?? "";
  return row.actor_name ? `${row.actor_name}${kind ? ` (${kind})` : ""}` : kind || "—";
}

function openDetail(group: ActivityGroup) {
  selectedLogs.value = group.logs;
  showDetail.value = true;
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

function matchesEnrollment(row: RecognitionLogOut) {
  if (row.entity_id === props.enrollmentId) return true;
  return !!row.label && row.label.toLowerCase() === props.label.toLowerCase();
}

async function fetchPage(append: boolean) {
  if (append) {
    if (loadingMore.value || !hasMore.value) return;
    loadingMore.value = true;
  } else {
    loading.value = true;
  }
  try {
    const offset = append ? rows.value.length : 0;
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(offset),
      entity_id: props.enrollmentId,
    });
    const res = await api<RecognitionLogListOut>(`/v1/admin/logs?${params}`);
    if (append) {
      const seen = new Set(rows.value.map((row) => row.id));
      rows.value = [...rows.value, ...res.items.filter((row) => !seen.has(row.id))];
    } else {
      rows.value = res.items;
    }
    total.value = res.total;
  } catch (e) {
    if (!append) {
      rows.value = [];
      total.value = 0;
      message.error(loadFailureMessage(e, "Failed to load activity"));
    }
  } finally {
    loading.value = false;
    loadingMore.value = false;
  }
}

function onTableScroll(e: Event) {
  const el = e.target as HTMLElement | null;
  if (!el || loadingMore.value || !hasMore.value) return;
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 120) {
    void fetchPage(true);
  }
}

useEventStream((event) => {
  const log = event.log;
  if (!log || event.type !== "recognition.log") return;
  if (!matchesEnrollment(log)) return;
  if (rows.value.some((row) => row.id === log.id)) return;
  rows.value = [log, ...rows.value];
  total.value += 1;
});

watch(
  () => props.enrollmentId,
  () => {
    void fetchPage(false);
  },
);

onMounted(() => {
  void fetchPage(false);
});
</script>

<template>
  <div class="activity-panel">
    <p v-if="rows.length" class="or-muted or-small">
      {{ rows.length }}{{ hasMore ? ` of ${total}` : "" }}
      event{{ total === 1 ? "" : "s" }}
      <template v-if="loadingMore"> · loading more</template>
    </p>
    <ContentSkeleton v-if="loading && !rows.length" variant="table" />
    <EmptyState
      v-else-if="!loading && !rows.length"
      title="No activity yet"
      description="Recognize this name or add samples. Events show up here."
      :icon="DocumentTextOutline"
    />
    <div v-else class="or-table-wrap activity-table">
      <NDataTable
        :columns="columns"
        :data="groups"
        :loading="loading && !loadingMore"
        :bordered="false"
        flex-height
        virtual-scroll
        :header-height="44"
        :min-row-height="48"
        :scroll-x="860"
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
.activity-panel {
  display: flex;
  flex-direction: column;
  gap: var(--or-space-3);
  min-height: 0;
}

.activity-table {
  min-height: 420px;
  height: min(70vh, 640px);
  display: flex;
  flex-direction: column;
}

.activity-table :deep(.n-data-table) {
  flex: 1;
  height: 100%;
}

:deep(.muted-cell) {
  color: var(--n-text-color-3);
}
</style>
