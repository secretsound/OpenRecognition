<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NDataTable,
  NButton,
  NSkeleton,
  NIcon,
  NInput,
  NSelect,
  NDropdown,
  useMessage,
} from "naive-ui";
import type { DataTableColumns, SelectOption } from "naive-ui";
import { AddOutline, EllipsisVerticalOutline } from "@vicons/ionicons5";
import { api, loadFailureMessage } from "@/api/client";
import type { EnrollmentOut } from "@/types/api";
import AppPageHeader from "@/components/AppPageHeader.vue";
import EmptyState from "@/components/EmptyState.vue";
import StatusPill from "@/components/StatusPill.vue";
import TestModalityDialog from "@/components/TestModalityDialog.vue";
import { resolveTestModalityFor, type TestModality } from "@/utils/testModality";
import TypeTag from "@/components/TypeTag.vue";
import { PeopleOutline } from "@vicons/ionicons5";

const router = useRouter();
const message = useMessage();
const loading = ref(true);
const loadError = ref<string | null>(null);
const rows = ref<EnrollmentOut[]>([]);
const search = ref("");
const typeFilter = ref<string | null>(null);
const showTestChooser = ref(false);
const testTarget = ref<EnrollmentOut | null>(null);

const typeFilterOptions: SelectOption[] = [
  { label: "Person", value: "person" },
  { label: "Pet", value: "pet" },
  { label: "Object", value: "object" },
  { label: "Sound", value: "sound" },
];

const filteredRows = computed(() => {
  let list = rows.value;
  const q = search.value.trim().toLowerCase();
  if (q) list = list.filter((r) => r.label.toLowerCase().includes(q));
  if (typeFilter.value) list = list.filter((r) => r.type === typeFilter.value);
  return list;
});

function rowActions(row: EnrollmentOut) {
  return [
    { label: "View", key: "view" },
    { label: "Test", key: "test" },
    { label: row.enabled ? "Disable" : "Enable", key: "toggle" },
  ];
}

function pushTest(row: EnrollmentOut, modality: TestModality) {
  router.push({
    name: "test",
    query: { expect: row.label, modality, enrollmentId: row.id },
  });
}

async function startTest(row: EnrollmentOut) {
  const choice = await resolveTestModalityFor(row);
  if (choice === "choose") {
    testTarget.value = row;
    showTestChooser.value = true;
    return;
  }
  pushTest(row, choice);
}

function pickTestModality(modality: TestModality) {
  const row = testTarget.value;
  showTestChooser.value = false;
  if (row) pushTest(row, modality);
}

async function onRowAction(key: string, row: EnrollmentOut) {
  if (key === "view") router.push(`/enrollments/${row.id}`);
  else if (key === "test") {
    await startTest(row);
  } else if (key === "toggle") {
    try {
      await api(`/v1/enrollments/${row.id}`, {
        method: "PATCH",
        json: { enabled: !row.enabled },
      });
      await load();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "Update failed");
    }
  }
}

const columns: DataTableColumns<EnrollmentOut> = [
  {
    title: "Label",
    key: "label",
    minWidth: 140,
    ellipsis: { tooltip: true },
    sorter: (a, b) => a.label.localeCompare(b.label),
    render(row) {
      return row.label;
    },
  },
  {
    title: "Type",
    key: "type",
    width: 100,
    render(row) {
      return h(TypeTag, { type: row.type });
    },
  },
  {
    title: "Samples",
    key: "sample_count",
    width: 120,
    sorter: (a, b) => a.sample_count - b.sample_count,
  },
  {
    title: "Status",
    key: "status",
    width: 140,
    render(row) {
      return h(StatusPill, { enrollment: row });
    },
  },
  {
    title: "",
    key: "actions",
    width: 56,
    render(row) {
      return h(
        NDropdown,
        {
          options: rowActions(row),
          onSelect: (key: string) => onRowAction(key, row),
        },
        {
          default: () =>
            h(
              NButton,
              {
                quaternary: true,
                size: "small",
                "aria-label": `More actions for ${row.label}`,
                onClick: (e: Event) => e.stopPropagation(),
              },
              { icon: () => h(NIcon, null, () => h(EllipsisVerticalOutline)) },
            ),
        },
      );
    },
  },
];

function enrollmentRowProps(row: EnrollmentOut) {
  return {
    style: "cursor: pointer",
    onClick: () => router.push(`/enrollments/${row.id}`),
  };
}

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    rows.value = await api<EnrollmentOut[]>("/v1/enrollments");
  } catch (e) {
    loadError.value = loadFailureMessage(e, "Failed to load enrollments");
    message.error(loadError.value);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="library-page">
    <AppPageHeader
      title="Library"
      description="People, pets, objects, and sounds this server can recognize."
    >
      <template #action>
        <NButton type="primary" @click="router.push('/enrollments/new')">
          <template #icon>
            <NIcon><AddOutline /></NIcon>
          </template>
          Add
        </NButton>
      </template>
      <template #extra>
        <div class="library-toolbar">
          <NInput
            v-model:value="search"
            placeholder="Search by name"
            clearable
            style="width: min(100%, 240px)"
          />
          <NSelect
            v-model:value="typeFilter"
            :options="typeFilterOptions"
            placeholder="Type"
            clearable
            style="width: min(100%, 160px)"
          />
        </div>
      </template>
    </AppPageHeader>

    <NSkeleton v-if="loading && !rows.length" text :repeat="6" />
    <EmptyState
      v-else-if="!loading && loadError"
      title="Couldn't load the library"
      :description="loadError"
      action-label="Retry"
      @action="load"
    />
    <EmptyState
      v-else-if="!loading && rows.length === 0"
      title="Nothing enrolled yet"
      description="Add a person, pet, object, or sound to start recognizing them."
      :icon="PeopleOutline"
      action-label="Add"
      @action="router.push('/enrollments/new')"
    />
    <p v-else-if="!loading && filteredRows.length === 0" class="filter-empty">
      Nothing matches your search.
      <NButton text type="primary" size="small" @click="search = ''; typeFilter = null">
        Clear filters
      </NButton>
    </p>
    <template v-else>
      <div class="or-list-cards">
        <button
          v-for="row in filteredRows"
          :key="row.id"
          type="button"
          class="or-list-card"
          @click="router.push(`/enrollments/${row.id}`)"
        >
          <span class="or-list-card__title">{{ row.label }}</span>
          <span class="or-list-card__meta">
            <TypeTag :type="row.type" />
            <StatusPill :enrollment="row" />
            <span>{{ row.sample_count }} samples</span>
          </span>
        </button>
      </div>
      <div class="or-table-wrap or-table-desktop">
        <NDataTable
          :columns="columns"
          :data="filteredRows"
          :loading="loading"
          :bordered="false"
          size="medium"
          :row-key="(row: EnrollmentOut) => row.id"
          :row-props="enrollmentRowProps"
        />
      </div>
      <div class="admin-table-footer">
        <span class="admin-table-total">
          {{ filteredRows.length }}
          <template v-if="filteredRows.length !== rows.length"> of {{ rows.length }}</template>
        </span>
      </div>
    </template>
    <TestModalityDialog
      :show="showTestChooser"
      :label="testTarget?.label ?? 'This enrollment'"
      @update:show="showTestChooser = $event"
      @pick="pickTestModality"
    />
  </div>
</template>

<style scoped>
.library-page {
  display: flex;
  flex-direction: column;
  gap: var(--or-section-gap);
}

.library-page :deep(.app-page-header) {
  margin-bottom: 0;
}

.library-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--or-inline-gap);
}

.filter-empty {
  margin: 0;
  text-align: center;
  font-size: 0.875rem;
  color: var(--n-text-color-3);
}
</style>
