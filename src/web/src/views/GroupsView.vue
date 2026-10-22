<script setup lang="ts">
import { h, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { NDataTable, NButton, NModal, NForm, NFormItem, NInput, NTag, NIcon, useMessage } from "naive-ui";
import type { DataTableColumns, FormInst } from "naive-ui";
import { AddOutline, AlbumsOutline } from "@vicons/ionicons5";
import { api, loadFailureMessage, ApiError } from "@/api/client";
import type { GroupOut } from "@/types/api";
import PageHeader from "@/components/kit/PageHeader.vue";
import DataList from "@/components/kit/DataList.vue";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import EmptyState from "@/components/EmptyState.vue";
import TimeAgo from "@/components/kit/TimeAgo.vue";

const router = useRouter();
const message = useMessage();
const loading = ref(true);
const loadError = ref<string | null>(null);
const rows = ref<GroupOut[]>([]);
const showCreate = ref(false);
const creating = ref(false);
const createFormRef = ref<FormInst | null>(null);
const createForm = ref({
  name: "",
  description: "",
});

const columns: DataTableColumns<GroupOut> = [
  {
    title: "Name",
    key: "name",
    minWidth: 180,
    sorter: (a, b) => a.name.localeCompare(b.name),
    render(row) {
      return h("span", { class: "name-cell" }, [
        row.name,
        row.system
          ? h(
              NTag,
              { size: "small", round: true, bordered: false, style: "margin-left: 8px" },
              () => "built-in",
            )
          : null,
      ]);
    },
  },
  {
    title: "Role",
    key: "grants_role",
    width: 120,
    render(row) {
      if (!row.grants_role) return "—";
      return h(
        NTag,
        { size: "small", round: true, bordered: false, type: row.grants_role === "admin" ? "success" : "info" },
        () => row.grants_role,
      );
    },
  },
  {
    title: "Members",
    key: "member_count",
    width: 100,
    sorter: (a, b) => a.member_count - b.member_count,
  },
  {
    title: "Enrollments",
    key: "enrollment_count",
    width: 120,
    sorter: (a, b) => a.enrollment_count - b.enrollment_count,
    render(row) {
      if (row.grants_role === "admin") return "All";
      return String(row.enrollment_count);
    },
  },
  {
    title: "Created",
    key: "created_at",
    width: 140,
    render(row) {
      return h(TimeAgo, { value: row.created_at });
    },
  },
];

function rowProps(row: GroupOut) {
  return {
    style: "cursor: pointer",
    onClick: () => router.push(`/groups/${row.id}`),
  };
}

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    rows.value = await api<GroupOut[]>("/v1/auth/groups");
  } catch (e) {
    loadError.value = loadFailureMessage(e, "Failed to load groups");
    message.error(loadError.value);
  } finally {
    loading.value = false;
  }
}

async function create() {
  await createFormRef.value?.validate();
  creating.value = true;
  try {
    const created = await api<GroupOut>("/v1/auth/groups", {
      method: "POST",
      json: {
        name: createForm.value.name.trim(),
        description: createForm.value.description.trim(),
      },
    });
    message.success("Group created");
    showCreate.value = false;
    createForm.value = { name: "", description: "" };
    await router.push(`/groups/${created.id}`);
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to create group");
  } finally {
    creating.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="or-page">
    <PageHeader
      title="Groups"
      description="Share enrollments with people, or give them a role."
    >
      <template #action>
        <NButton type="primary" @click="showCreate = true">
          <template #icon>
            <NIcon><AddOutline /></NIcon>
          </template>
          Add group
        </NButton>
      </template>
    </PageHeader>

    <ContentSkeleton v-if="loading && !rows.length" variant="table" />
    <EmptyState
      v-else-if="!loading && loadError"
      title="Couldn't load groups"
      :description="loadError"
      action-label="Retry"
      @action="load"
    />
    <EmptyState
      v-else-if="!loading && rows.length === 0"
      title="No groups"
      description="Create a group to share a pet or person with someone."
      :icon="AlbumsOutline"
      action-label="Add group"
      @action="showCreate = true"
    />
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
              :row-key="(row: GroupOut) => row.id"
              :row-props="rowProps"
            />
          </div>
        </template>
        <template #card="{ item }">
          <button type="button" class="or-list-card" @click="router.push(`/groups/${item.id}`)">
            <span class="or-list-card__title">{{ item.name }}</span>
            <span class="or-list-card__meta">
              {{ item.member_count }} members
              · {{ item.grants_role === "admin" ? "all enrollments" : `${item.enrollment_count} enrollments` }}
            </span>
          </button>
        </template>
      </DataList>
      <p class="or-footer-count">
        {{ rows.length }} group{{ rows.length === 1 ? "" : "s" }}
      </p>
    </template>

    <NModal v-model:show="showCreate" preset="card" title="Add group" class="or-modal or-modal--narrow">
      <NForm ref="createFormRef" :model="createForm" label-placement="top">
        <NFormItem label="Name" path="name" :rule="{ required: true, message: 'Name is required' }">
          <NInput v-model:value="createForm.name" placeholder="Family pets" />
        </NFormItem>
        <NFormItem label="Description">
          <NInput
            v-model:value="createForm.description"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            placeholder="Who this group is for"
          />
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="or-modal-footer">
          <NButton @click="showCreate = false">Cancel</NButton>
          <NButton type="primary" :loading="creating" @click="create">Create</NButton>
        </div>
      </template>
    </NModal>
  </div>
</template>
