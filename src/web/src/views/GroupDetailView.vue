<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NSwitch,
  NTag,
  NDataTable,
  useDialog,
  useMessage,
} from "naive-ui";
import type { DataTableColumns, SelectOption } from "naive-ui";
import { api, ApiError } from "@/api/client";
import type { EnrollmentOut, GroupEnrollmentOut, GroupOut, UserOut } from "@/types/api";
import PageHeader from "@/components/kit/PageHeader.vue";
import SegmentedControl from "@/components/kit/SegmentedControl.vue";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import SettingsSection from "@/components/settings/SettingsSection.vue";
import SettingRow from "@/components/settings/SettingRow.vue";
import EmptyState from "@/components/EmptyState.vue";
import { useBreadcrumbTail } from "@/composables/useBreadcrumbTail";

type Tab = "members" | "enrollments" | "settings";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const dialog = useDialog();

const id = computed(() => route.params.id as string);
const loading = ref(true);
const group = ref<GroupOut | null>(null);
const users = ref<UserOut[]>([]);
const enrollments = ref<EnrollmentOut[]>([]);
const savingMembers = ref(false);
const savingEnrollments = ref(false);
const savingSettings = ref(false);
const deleting = ref(false);
const memberIds = ref<string[]>([]);
const assigned = ref<GroupEnrollmentOut[]>([]);
const addEnrollmentId = ref<string | null>(null);
const draftName = ref("");
const draftDescription = ref("");
const draftSso = ref("");

useBreadcrumbTail(computed(() => group.value?.name));

const seesAll = computed(() => group.value?.grants_role === "admin");

const tab = computed<Tab>({
  get() {
    const t = route.query.tab;
    if (t === "enrollments" && seesAll.value) return "members";
    if (t === "enrollments" || t === "settings") return t;
    return "members";
  },
  set(next) {
    router.replace({ query: { ...route.query, tab: next === "members" ? undefined : next } });
  },
});

const tabOptions = computed(() => {
  const options: { value: Tab; label: string }[] = [
    { value: "members", label: "Members" },
    { value: "settings", label: "Settings" },
  ];
  if (!seesAll.value) {
    options.splice(1, 0, { value: "enrollments", label: "Enrollments" });
  }
  return options;
});

const userOptions = computed<SelectOption[]>(() =>
  users.value.map((u) => ({ label: `${u.username} (${u.role})`, value: u.id })),
);

const enrollmentOptions = computed<SelectOption[]>(() => {
  const taken = new Set(assigned.value.map((e) => e.enrollment_id));
  return enrollments.value
    .filter((e) => !taken.has(e.id))
    .map((e) => ({ label: `${e.label} · ${e.type}`, value: e.id }));
});

const membersDirty = computed(() => {
  if (!group.value) return false;
  const current = [...group.value.members.map((m) => m.id)].sort();
  const next = [...memberIds.value].sort();
  return current.join() !== next.join();
});

const enrollmentsDirty = computed(() => {
  if (!group.value) return false;
  const current = group.value.enrollments;
  if (current.length !== assigned.value.length) return true;
  const byId = new Map(current.map((e) => [e.enrollment_id, e]));
  return assigned.value.some((e) => {
    const saved = byId.get(e.enrollment_id);
    return (
      !saved ||
      saved.can_add_samples !== e.can_add_samples ||
      saved.can_manage !== e.can_manage
    );
  });
});

const settingsDirty = computed(() => {
  if (!group.value) return false;
  return (
    draftName.value.trim() !== group.value.name ||
    draftDescription.value.trim() !== (group.value.description || "") ||
    draftSso.value.trim() !== (group.value.sso_name || "")
  );
});

function applyGroup(next: GroupOut) {
  group.value = next;
  memberIds.value = next.members.map((m) => m.id);
  assigned.value = next.enrollments.map((e) => ({ ...e }));
  draftName.value = next.name;
  draftDescription.value = next.description || "";
  draftSso.value = next.sso_name || "";
}

async function load() {
  loading.value = true;
  try {
    const [g, userRows, library] = await Promise.all([
      api<GroupOut>(`/v1/auth/groups/${id.value}`),
      api<UserOut[]>("/v1/auth/users"),
      api<EnrollmentOut[]>("/v1/enrollments"),
    ]);
    applyGroup(g);
    users.value = userRows;
    enrollments.value = library;
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load group");
    router.push("/groups");
  } finally {
    loading.value = false;
  }
}

async function saveMembers() {
  if (!group.value) return;
  savingMembers.value = true;
  try {
    applyGroup(
      await api<GroupOut>(`/v1/auth/groups/${group.value.id}/members`, {
        method: "PUT",
        json: { user_ids: memberIds.value },
      }),
    );
    message.success("Members updated");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not update members");
  } finally {
    savingMembers.value = false;
  }
}

function addEnrollment() {
  if (!addEnrollmentId.value) return;
  const en = enrollments.value.find((e) => e.id === addEnrollmentId.value);
  if (!en) return;
  assigned.value = [
    ...assigned.value,
    {
      enrollment_id: en.id,
      label: en.label,
      type: en.type,
      can_add_samples: true,
      can_manage: false,
    },
  ];
  addEnrollmentId.value = null;
}

function removeAssigned(enrollmentId: string) {
  assigned.value = assigned.value.filter((e) => e.enrollment_id !== enrollmentId);
}

async function saveEnrollments() {
  if (!group.value) return;
  savingEnrollments.value = true;
  try {
    applyGroup(
      await api<GroupOut>(`/v1/auth/groups/${group.value.id}/enrollments`, {
        method: "PUT",
        json: {
          enrollments: assigned.value.map((e) => ({
            enrollment_id: e.enrollment_id,
            can_add_samples: e.can_add_samples,
            can_manage: e.can_manage,
          })),
        },
      }),
    );
    message.success("Enrollments updated");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not update enrollments");
  } finally {
    savingEnrollments.value = false;
  }
}

async function saveSettings() {
  if (!group.value) return;
  savingSettings.value = true;
  try {
    applyGroup(
      await api<GroupOut>(`/v1/auth/groups/${group.value.id}`, {
        method: "PATCH",
        json: {
          name: draftName.value.trim(),
          description: draftDescription.value.trim(),
          sso_name: draftSso.value.trim() || null,
        },
      }),
    );
    message.success("Settings saved");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Save failed");
  } finally {
    savingSettings.value = false;
  }
}

function removeGroup() {
  dialog.warning({
    title: "Delete this group?",
    content: "Members lose these enrollment rights. Built-in groups cannot be deleted.",
    positiveText: "Delete",
    negativeText: "Cancel",
    onPositiveClick: async () => {
      deleting.value = true;
      try {
        await api(`/v1/auth/groups/${id.value}`, { method: "DELETE" });
        message.success("Deleted");
        router.push("/groups");
      } catch (e) {
        message.error(e instanceof ApiError ? e.message : "Delete failed");
      } finally {
        deleting.value = false;
      }
    },
  });
}

const assignedColumns: DataTableColumns<GroupEnrollmentOut> = [
  {
    title: "Name",
    key: "label",
    minWidth: 160,
    render(row) {
      return h("span", {}, [row.label, " ", h("span", { class: "or-muted or-small" }, row.type)]);
    },
  },
  {
    title: "Add samples",
    key: "can_add_samples",
    width: 130,
    render(row) {
      return h(NSwitch, {
        value: row.can_add_samples,
        onUpdateValue: (v: boolean) => {
          assigned.value = assigned.value.map((item) =>
            item.enrollment_id === row.enrollment_id ? { ...item, can_add_samples: v } : item,
          );
        },
      });
    },
  },
  {
    title: "Manage",
    key: "can_manage",
    width: 110,
    render(row) {
      return h(NSwitch, {
        value: row.can_manage,
        onUpdateValue: (v: boolean) => {
          assigned.value = assigned.value.map((item) =>
            item.enrollment_id === row.enrollment_id ? { ...item, can_manage: v } : item,
          );
        },
      });
    },
  },
  {
    title: "",
    key: "remove",
    width: 88,
    render(row) {
      return h(
        NButton,
        { size: "small", quaternary: true, onClick: () => removeAssigned(row.enrollment_id) },
        { default: () => "Remove" },
      );
    },
  },
];

watch(id, () => {
  void load();
});

onMounted(load);
</script>

<template>
  <div class="or-page">
    <ContentSkeleton v-if="loading" variant="detail" />
    <template v-else-if="group">
      <PageHeader :title="group.name" :description="group.description || 'Assign people and enrollments.'">
        <template #meta>
          <NTag v-if="group.system" size="small" round :bordered="false">Built-in</NTag>
          <NTag v-if="group.grants_role" size="small" round :bordered="false" type="success">
            Grants {{ group.grants_role }}
          </NTag>
          <span class="or-muted or-small">{{ group.member_count }} members</span>
          <span v-if="!seesAll" class="or-muted or-small">{{ group.enrollment_count }} enrollments</span>
        </template>
        <template #action>
          <NButton v-if="!group.system" :loading="deleting" @click="removeGroup">Delete</NButton>
        </template>
        <template #tabs>
          <SegmentedControl v-model="tab" aria-label="Group sections" :options="tabOptions" />
        </template>
      </PageHeader>

      <section v-if="tab === 'members'" class="or-stack">
        <SettingsSection
          title="Members"
          :description="
            seesAll
              ? 'People in this group can see every enrollment and manage the server.'
              : 'People in this group share the enrollments assigned on the next tab.'
          "
        >
          <NSelect
            v-model:value="memberIds"
            multiple
            filterable
            :options="userOptions"
            placeholder="Add people"
          />
          <div class="row-end">
            <NButton type="primary" :disabled="!membersDirty" :loading="savingMembers" @click="saveMembers">
              Save members
            </NButton>
          </div>
        </SettingsSection>
      </section>

      <section v-else-if="tab === 'enrollments'" class="or-stack">
        <SettingsSection
          title="Enrollments"
          description="Viewers in this group only see these names. Add samples lets them teach. Manage lets them change settings."
        >
          <div class="add-row">
            <NSelect
              v-model:value="addEnrollmentId"
              filterable
              clearable
              :options="enrollmentOptions"
              placeholder="Add an enrollment"
            />
            <NButton :disabled="!addEnrollmentId" @click="addEnrollment">Add</NButton>
          </div>
          <EmptyState
            v-if="!assigned.length"
            title="No enrollments yet"
            description="Add a pet or person this group should see."
          />
          <div v-else class="or-table-wrap">
            <NDataTable
              :columns="assignedColumns"
              :data="assigned"
              :bordered="false"
              :row-key="(row: GroupEnrollmentOut) => row.enrollment_id"
            />
          </div>
          <div class="row-end">
            <NButton
              type="primary"
              :disabled="!enrollmentsDirty"
              :loading="savingEnrollments"
              @click="saveEnrollments"
            >
              Save enrollments
            </NButton>
          </div>
        </SettingsSection>
      </section>

      <section v-else class="or-stack">
        <SettingsSection title="Group">
          <NForm label-placement="top">
            <NFormItem label="Name">
              <NInput v-model:value="draftName" />
            </NFormItem>
            <NFormItem label="Description">
              <NInput
                v-model:value="draftDescription"
                type="textarea"
                :autosize="{ minRows: 2, maxRows: 4 }"
              />
            </NFormItem>
            <NFormItem label="SSO name">
              <NInput v-model:value="draftSso" placeholder="admin" />
              <p class="or-muted or-small">
                A provider group with this name is added here when someone signs in.
              </p>
            </NFormItem>
          </NForm>
          <SettingRow
            v-if="group.grants_role"
            label="Role grant"
            hint="Built-in groups raise a member's role. Custom groups only share enrollments."
          >
            <NTag size="small" round :bordered="false">{{ group.grants_role }}</NTag>
          </SettingRow>
          <div class="row-end">
            <NButton type="primary" :disabled="!settingsDirty" :loading="savingSettings" @click="saveSettings">
              Save
            </NButton>
          </div>
        </SettingsSection>
      </section>
    </template>
  </div>
</template>

<style scoped>
.add-row {
  display: flex;
  gap: var(--or-space-2);
  align-items: center;
}

.add-row :deep(.n-select) {
  flex: 1;
}

.row-end {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--or-space-4);
}
</style>
