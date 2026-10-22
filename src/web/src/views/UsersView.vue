<script setup lang="ts">
import { h, onMounted, ref } from "vue";
import {
  NDataTable,
  NButton,
  NModal,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NTag,
  NPopconfirm,
  NIcon,
  useMessage,
} from "naive-ui";
import type { DataTableColumns, FormInst, SelectOption } from "naive-ui";
import { AddOutline, TrashOutline, CreateOutline } from "@vicons/ionicons5";
import { api, loadFailureMessage } from "@/api/client";
import type { UserOut } from "@/types/api";
import PageHeader from "@/components/kit/PageHeader.vue";
import DataList from "@/components/kit/DataList.vue";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import EmptyState from "@/components/EmptyState.vue";
import { PeopleCircleOutline } from "@vicons/ionicons5";
import { ApiError } from "@/api/client";
import { useAuth } from "@/composables/useAuth";

const message = useMessage();
const { username: currentUsername } = useAuth();
const loading = ref(true);
const loadError = ref<string | null>(null);
const rows = ref<UserOut[]>([]);
const showCreate = ref(false);
const showEdit = ref(false);
const creating = ref(false);
const saving = ref(false);
const createFormRef = ref<FormInst | null>(null);
const editFormRef = ref<FormInst | null>(null);
const editingUser = ref<UserOut | null>(null);
const createForm = ref({
  username: "",
  password: "",
  role: "operator",
});

const editForm = ref({
  role: "operator",
  password: "",
});

const roleOptions: SelectOption[] = [
  { label: "Admin — full access", value: "admin" },
  { label: "Operator — enroll & recognize", value: "operator" },
  { label: "Viewer — read only", value: "viewer" },
];

const roleTagType = (role: string) => {
  if (role === "admin") return "success";
  if (role === "operator") return "info";
  return "default";
};

const columns: DataTableColumns<UserOut> = [
  {
    title: "Username",
    key: "username",
    minWidth: 140,
    ellipsis: { tooltip: true },
    sorter: (a, b) => a.username.localeCompare(b.username),
    render(row) {
      const you = row.username === currentUsername.value;
      return h("span", {}, [
        row.username,
        you
          ? h(
              NTag,
              { size: "small", round: true, bordered: false, style: "margin-left: 8px" },
              () => "you",
            )
          : null,
      ]);
    },
  },
  {
    title: "Role",
    key: "role",
    width: 120,
    render(row) {
      return h(
        NTag,
        { size: "small", type: roleTagType(row.role), round: true, bordered: false },
        () => row.role,
      );
    },
  },
  {
    title: "Created",
    key: "created_at",
    width: 168,
    sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    render(row) {
      return new Date(row.created_at).toLocaleString();
    },
  },
  {
    title: "",
    key: "actions",
    width: 88,
    fixed: "right",
    render(row) {
      return h("div", { class: "row-actions", onClick: (e: Event) => e.stopPropagation() }, [
        h(
          NButton,
          {
            quaternary: true,
            size: "small",
            "aria-label": `Edit ${row.username}`,
            onClick: () => openEdit(row),
          },
          { icon: () => h(NIcon, null, { default: () => h(CreateOutline) }) },
        ),
        h(
          NPopconfirm,
          { onPositiveClick: () => remove(row.id) },
          {
            trigger: () =>
              h(
                NButton,
                {
                  quaternary: true,
                  size: "small",
                  "aria-label": `Delete ${row.username}`,
                  disabled: row.username === currentUsername.value,
                },
                { icon: () => h(NIcon, null, { default: () => h(TrashOutline) }) },
              ),
            default: () => `Delete user "${row.username}"?`,
          },
        ),
      ]);
    },
  },
];

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    rows.value = await api<UserOut[]>("/v1/auth/users");
  } catch (e) {
    loadError.value = loadFailureMessage(e, "Failed to load users");
    message.error(loadError.value);
  } finally {
    loading.value = false;
  }
}

async function create() {
  await createFormRef.value?.validate();
  creating.value = true;
  try {
    await api<UserOut>("/v1/auth/users", {
      method: "POST",
      json: {
        username: createForm.value.username.trim(),
        password: createForm.value.password,
        role: createForm.value.role,
      },
    });
    message.success("User created");
    showCreate.value = false;
    createForm.value = { username: "", password: "", role: "operator" };
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to create user");
  } finally {
    creating.value = false;
  }
}

function openEdit(user: UserOut) {
  editingUser.value = user;
  editForm.value = { role: user.role, password: "" };
  showEdit.value = true;
}

async function saveEdit() {
  if (!editingUser.value) return;
  if (!editForm.value.password && editForm.value.role === editingUser.value.role) {
    message.warning("Change role or set a new password");
    return;
  }
  saving.value = true;
  try {
    const patch: { role?: string; password?: string } = {};
    if (editForm.value.role !== editingUser.value.role) {
      patch.role = editForm.value.role;
    }
    if (editForm.value.password) {
      patch.password = editForm.value.password;
    }
    await api<UserOut>(`/v1/auth/users/${editingUser.value.id}`, {
      method: "PATCH",
      json: patch,
    });
    message.success("User updated");
    showEdit.value = false;
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to update user");
  } finally {
    saving.value = false;
  }
}

async function remove(userId: string) {
  try {
    await api(`/v1/auth/users/${userId}`, { method: "DELETE" });
    message.success("User deleted");
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to delete user");
  }
}

onMounted(load);
</script>

<template>
  <div class="or-page">
    <PageHeader
      title="Users"
      description="Manage who can sign in to the admin console."
    >
      <template #action>
        <NButton type="primary" @click="showCreate = true">
          <template #icon>
            <NIcon><AddOutline /></NIcon>
          </template>
          Add user
        </NButton>
      </template>
    </PageHeader>

    <ContentSkeleton v-if="loading && !rows.length" variant="table" />
    <EmptyState
      v-else-if="!loading && loadError"
      title="Couldn't load users"
      :description="loadError"
      action-label="Retry"
      @action="load"
    />
    <EmptyState
      v-else-if="!loading && rows.length === 0"
      title="No users"
      description="Create accounts for teammates who need access to the console."
      :icon="PeopleCircleOutline"
      action-label="Add user"
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
              :row-key="(row: UserOut) => row.id"
            />
          </div>
        </template>
        <template #card="{ item }">
          <div class="or-list-card user-card">
            <span class="or-list-card__title">
              {{ item.username }}
              <NTag v-if="item.username === currentUsername" size="small" round :bordered="false">you</NTag>
            </span>
            <span class="or-list-card__meta">
              <NTag size="small" round :bordered="false" :type="roleTagType(item.role)">{{ item.role }}</NTag>
              <NButton size="small" quaternary :aria-label="`Edit ${item.username}`" @click="openEdit(item)">
                Edit
              </NButton>
            </span>
          </div>
        </template>
      </DataList>
      <p class="or-footer-count">
        {{ rows.length }} user{{ rows.length === 1 ? "" : "s" }}
      </p>
    </template>

    <NModal v-model:show="showCreate" preset="card" title="Add user" class="or-modal or-modal--narrow">
      <NForm ref="createFormRef" :model="createForm" label-placement="top">
        <NFormItem
          label="Username"
          path="username"
          :rule="{ required: true, message: 'Username is required' }"
        >
          <NInput v-model:value="createForm.username" placeholder="jane" autocomplete="off" />
        </NFormItem>
        <NFormItem
          label="Password"
          path="password"
          :rule="{ required: true, message: 'Password is required', min: 4 }"
        >
          <NInput
            v-model:value="createForm.password"
            type="password"
            show-password-on="click"
            placeholder="Password"
            autocomplete="new-password"
          />
        </NFormItem>
        <NFormItem label="Role">
          <NSelect v-model:value="createForm.role" :options="roleOptions" />
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="or-modal-footer">
          <NButton @click="showCreate = false">Cancel</NButton>
          <NButton type="primary" :loading="creating" @click="create">Create</NButton>
        </div>
      </template>
    </NModal>

    <NModal
      v-model:show="showEdit"
      preset="card"
      :title="`Edit ${editingUser?.username ?? 'user'}`"
      class="or-modal or-modal--narrow"
    >
      <NForm ref="editFormRef" :model="editForm" label-placement="top">
        <NFormItem label="Role">
          <NSelect v-model:value="editForm.role" :options="roleOptions" />
        </NFormItem>
        <NFormItem label="New password">
          <NInput
            v-model:value="editForm.password"
            type="password"
            show-password-on="click"
            placeholder="Leave blank to keep current"
            autocomplete="new-password"
          />
        </NFormItem>
        <p class="edit-hint">Setting a new password signs the user out of all sessions.</p>
      </NForm>
      <template #footer>
        <div class="or-modal-footer">
          <NButton @click="showEdit = false">Cancel</NButton>
          <NButton type="primary" :loading="saving" @click="saveEdit">Save</NButton>
        </div>
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.user-card {
  cursor: default;
  width: 100%;
  text-align: left;
}

.edit-hint {
  margin: 0;
  color: var(--n-text-color-3);
  font-size: 0.8rem;
}

:deep(.row-actions) {
  display: flex;
  gap: 4px;
  align-items: center;
}
</style>
