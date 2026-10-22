<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  NDataTable,
  NButton,
  NIcon,
  NInput,
  NDropdown,
  useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import { AddOutline, EllipsisVerticalOutline, PeopleOutline } from "@vicons/ionicons5";
import { api, loadFailureMessage } from "@/api/client";
import type { EnrollmentOut, EnrollmentType } from "@/types/api";
import PageHeader from "@/components/kit/PageHeader.vue";
import FilterBar from "@/components/kit/FilterBar.vue";
import DataList from "@/components/kit/DataList.vue";
import ProfileMark from "@/components/kit/ProfileMark.vue";
import Chip from "@/components/kit/Chip.vue";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import EmptyState from "@/components/EmptyState.vue";
import StatusPill from "@/components/StatusPill.vue";
import TypeTag from "@/components/TypeTag.vue";
import TestModalityDialog from "@/components/TestModalityDialog.vue";
import { resolveTestModalityFor, type TestModality } from "@/utils/testModality";
import { canWrite } from "@/utils/roles";
import { useAuth } from "@/composables/useAuth";

const router = useRouter();
const message = useMessage();
const { role } = useAuth();
const loading = ref(true);
const loadError = ref<string | null>(null);
const rows = ref<EnrollmentOut[]>([]);
const search = ref("");
const typeFilter = ref<EnrollmentType | "all">("all");
const showTestChooser = ref(false);
const testTarget = ref<EnrollmentOut | null>(null);

const typeChips: { value: EnrollmentType | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "person", label: "People" },
  { value: "pet", label: "Pets" },
  { value: "object", label: "Objects" },
  { value: "sound", label: "Sounds" },
];

const filtersActive = computed(() => search.value.trim().length > 0 || typeFilter.value !== "all");

function modalityChips(row: EnrollmentOut) {
  const mods = row.quality?.modalities ?? [];
  return mods
    .filter((m) => m.sample_count > 0)
    .map((m) => ({
      key: m.modality,
      label: `${m.sample_count} ${m.modality === "audio" ? "voice" : m.modality === "image" ? "face" : m.modality}`,
      tone: (m.modality === "audio" ? "audio" : m.modality === "image" ? "image" : "default") as
        | "audio"
        | "image"
        | "default",
    }));
}

function rowActions(row: EnrollmentOut) {
  return [
    { label: "Open", key: "view" },
    { label: "Recognize", key: "test" },
    { label: row.enabled ? "Turn off" : "Turn on", key: "toggle" },
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
  else if (key === "test") await startTest(row);
  else if (key === "toggle") {
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
    title: "Name",
    key: "label",
    minWidth: 200,
    sorter: (a, b) => a.label.localeCompare(b.label),
    render(row) {
      return h("div", { class: "name-cell" }, [
        h(ProfileMark, { label: row.label, type: row.type, size: "sm" }),
        h("span", { class: "name-cell__label" }, row.label),
      ]);
    },
  },
  {
    title: "Type",
    key: "type",
    width: 120,
    render(row) {
      return h(TypeTag, { type: row.type });
    },
  },
  {
    title: "Samples",
    key: "samples",
    minWidth: 160,
    render(row) {
      const chips = modalityChips(row);
      if (!chips.length) return `${row.sample_count}`;
      return h(
        "div",
        { class: "chip-row" },
        chips.map((c) => h(Chip, { tone: c.tone }, { default: () => c.label })),
      );
    },
  },
  {
    title: "Status",
    key: "status",
    width: 150,
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
        { options: rowActions(row), onSelect: (key: string) => onRowAction(key, row) },
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
    const params = new URLSearchParams();
    const q = search.value.trim();
    if (q) params.set("q", q);
    if (typeFilter.value !== "all") params.set("type", typeFilter.value);
    const qs = params.toString();
    rows.value = await api<EnrollmentOut[]>(qs ? `/v1/enrollments?${qs}` : "/v1/enrollments");
  } catch (e) {
    loadError.value = loadFailureMessage(e, "Failed to load the library");
    message.error(loadError.value);
  } finally {
    loading.value = false;
  }
}

function clearFilters() {
  search.value = "";
  typeFilter.value = "all";
}

let searchTimer: ReturnType<typeof setTimeout> | null = null;
watch(search, () => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    void load();
  }, 250);
});
watch(typeFilter, () => {
  if (searchTimer) clearTimeout(searchTimer);
  void load();
});

onMounted(load);
</script>

<template>
  <div class="or-page">
    <PageHeader title="Library" description="People, pets, objects, and sounds this server can recognize.">
      <template v-if="canWrite(role)" #action>
        <NButton type="primary" @click="router.push('/enrollments/new')">
          <template #icon>
            <NIcon><AddOutline /></NIcon>
          </template>
          Add
        </NButton>
      </template>
      <template #extra>
        <FilterBar :active="filtersActive" @clear="clearFilters">
          <NInput
            v-model:value="search"
            placeholder="Search by name"
            clearable
            style="width: min(100%, 240px)"
          />
          <div class="type-chips">
            <button
              v-for="chip in typeChips"
              :key="chip.value"
              type="button"
              class="or-chip or-chip--sm"
              :class="typeFilter === chip.value ? 'or-chip--accent' : 'or-chip--default'"
              @click="typeFilter = chip.value"
            >
              {{ chip.label }}
            </button>
          </div>
        </FilterBar>
      </template>
    </PageHeader>

    <ContentSkeleton v-if="loading && !rows.length" variant="table" />
    <EmptyState
      v-else-if="!loading && loadError"
      title="Couldn't load the library"
      :description="loadError"
      action-label="Retry"
      @action="load"
    />
    <EmptyState
      v-else-if="!loading && rows.length === 0 && !filtersActive"
      title="Nothing enrolled yet"
      description="Add a person, pet, object, or sound to start recognizing them."
      :icon="PeopleOutline"
      action-label="Add"
      @action="router.push('/enrollments/new')"
    />
    <p v-else-if="!loading && rows.length === 0 && filtersActive" class="or-muted" style="text-align: center">
      Nothing matches.
    </p>
    <template v-else>
      <DataList :items="rows" :get-key="(row) => row.id">
        <template #table>
          <div class="or-table-wrap">
            <NDataTable
              :columns="columns"
              :data="rows"
              :loading="loading"
              :bordered="false"
              size="medium"
              :row-key="(row: EnrollmentOut) => row.id"
              :row-props="enrollmentRowProps"
            />
          </div>
        </template>
        <template #card="{ item }">
          <button type="button" class="or-list-card" @click="router.push(`/enrollments/${item.id}`)">
            <span class="person-row">
              <ProfileMark :label="item.label" :type="item.type" />
              <span class="or-list-card__title">{{ item.label }}</span>
            </span>
            <span class="or-list-card__meta">
              <TypeTag :type="item.type" />
              <StatusPill :enrollment="item" />
              <span>{{ item.sample_count }} samples</span>
            </span>
          </button>
        </template>
      </DataList>
      <p class="or-footer-count">
        {{ rows.length }} {{ filtersActive ? "matching" : "in the library" }}
      </p>
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
.type-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.person-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

:deep(.name-cell) {
  display: flex;
  align-items: center;
  gap: 10px;
}

:deep(.name-cell__label) {
  font-weight: 500;
}

:deep(.chip-row) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
