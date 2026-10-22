<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NDataTable,
  NButton,
  NModal,
  NPopconfirm,
  NIcon,
  NAlert,
  NCode,
  useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import { AddOutline, TrashOutline, CopyOutline, CreateOutline, KeyOutline } from "@vicons/ionicons5";
import { api, ApiError, loadFailureMessage } from "@/api/client";
import type { ApiKeyCreated, ApiKeyOut } from "@/types/api";
import PageHeader from "@/components/kit/PageHeader.vue";
import DataList from "@/components/kit/DataList.vue";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import EmptyState from "@/components/EmptyState.vue";
import Chip from "@/components/kit/Chip.vue";
import TimeAgo from "@/components/kit/TimeAgo.vue";
import CreateApiKeyModal from "@/components/CreateApiKeyModal.vue";
import { useMcpCatalog } from "@/composables/useMcpCatalog";
import { permissionChips, type KeyPreset } from "@/utils/keyPermissions";

const message = useMessage();
const route = useRoute();
const router = useRouter();
const { ensureCatalog, hostConfigWithKey } = useMcpCatalog();

const loading = ref(true);
const loadError = ref<string | null>(null);
const rows = ref<ApiKeyOut[]>([]);
const showEditor = ref(false);
const createPreset = ref<KeyPreset>("default");
const editing = ref<ApiKeyOut | null>(null);
const showKeyModal = ref(false);
const createdKey = ref<string | null>(null);
const revokingId = ref<string | null>(null);

const mcpHostConfig = computed(() =>
  createdKey.value ? hostConfigWithKey(createdKey.value) : "",
);

function openCreate(preset: KeyPreset = "default") {
  editing.value = null;
  createPreset.value = preset;
  showEditor.value = true;
}

function openEdit(row: ApiKeyOut) {
  editing.value = row;
  showEditor.value = true;
}

function onKeyCreated(res: ApiKeyCreated) {
  createdKey.value = res.key;
  showKeyModal.value = true;
  if (route.query.for === "mcp") {
    router.replace({ path: "/keys" });
  }
  void load();
}

function permissionCell(scopes: string[]) {
  const chips = permissionChips(scopes);
  if (!chips.length) return h("span", { class: "muted-cell" }, "None");
  return h(
    "span",
    { class: "key-perms" },
    chips.map((chip) => h(Chip, { key: chip.id, tone: chip.tone, size: "sm" }, () => chip.label)),
  );
}

const columns: DataTableColumns<ApiKeyOut> = [
  {
    title: "Name",
    key: "name",
    minWidth: 160,
    ellipsis: { tooltip: true },
    sorter: (a, b) => a.name.localeCompare(b.name),
    render(row) {
      return h("span", { class: "key-name" }, row.name);
    },
  },
  {
    title: "Permissions",
    key: "scopes",
    minWidth: 220,
    render(row) {
      return permissionCell(row.scopes);
    },
  },
  {
    title: "Last used",
    key: "last_used_at",
    width: 140,
    render(row) {
      return row.last_used_at
        ? h(TimeAgo, { value: row.last_used_at })
        : h("span", { class: "muted-cell" }, "Never");
    },
  },
  {
    title: "Created",
    key: "created_at",
    width: 140,
    sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    render(row) {
      return h(TimeAgo, { value: row.created_at });
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
            "aria-label": `Edit ${row.name}`,
            onClick: () => openEdit(row),
          },
          { icon: () => h(NIcon, null, { default: () => h(CreateOutline) }) },
        ),
        h(
          NPopconfirm,
          {
            onPositiveClick: () => {
              void revoke(row.id);
            },
          },
          {
            trigger: () =>
              h(
                NButton,
                {
                  quaternary: true,
                  size: "small",
                  "aria-label": `Delete ${row.name}`,
                  loading: revokingId.value === row.id,
                },
                { icon: () => h(NIcon, null, { default: () => h(TrashOutline) }) },
              ),
            default: () => `Delete “${row.name}”? Apps and assistants using it will stop working.`,
          },
        ),
      ]);
    },
  },
];

function rowProps(row: ApiKeyOut) {
  return {
    style: "cursor: pointer",
    onClick: () => openEdit(row),
  };
}

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    rows.value = await api<ApiKeyOut[]>("/v1/auth/keys");
  } catch (e) {
    loadError.value = loadFailureMessage(e, "Failed to load keys");
    message.error(loadError.value);
  } finally {
    loading.value = false;
  }
}

async function revoke(keyId: string) {
  revokingId.value = keyId;
  try {
    await api(`/v1/auth/keys/${keyId}`, { method: "DELETE" });
    message.success("API key deleted");
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to delete key");
  } finally {
    revokingId.value = null;
  }
}

async function copyText(text: string, label: string) {
  try {
    await navigator.clipboard.writeText(text);
    message.success(`Copied ${label}`);
  } catch {
    message.error("Could not copy");
  }
}

onMounted(async () => {
  await Promise.all([load(), ensureCatalog().catch(() => null)]);
  if (route.query.for === "mcp") openCreate("mcp");
});

watch(
  () => route.query.for,
  (value) => {
    if (value === "mcp" && !showEditor.value) openCreate("mcp");
  },
);
</script>

<template>
  <div class="or-page">
    <PageHeader
      title="API keys"
      description="Keys let apps and assistants call this server. Each permission works the same way over the REST API and over MCP."
    >
      <template #action>
        <NButton type="primary" @click="openCreate('default')">
          <template #icon>
            <NIcon><AddOutline /></NIcon>
          </template>
          Create key
        </NButton>
      </template>
    </PageHeader>

    <ContentSkeleton v-if="loading && !rows.length" variant="table" />
    <EmptyState
      v-else-if="!loading && loadError"
      title="Couldn't load API keys"
      :description="loadError"
      action-label="Retry"
      @action="load"
    />
    <EmptyState
      v-else-if="!loading && rows.length === 0"
      title="No API keys"
      description="Create a key for Home Assistant, an assistant, or any other app that should call this server."
      :icon="KeyOutline"
      action-label="Create key"
      @action="openCreate('default')"
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
              :row-key="(row: ApiKeyOut) => row.id"
              :row-props="rowProps"
            />
          </div>
        </template>
        <template #card="{ item }">
          <div class="or-list-card key-card" @click="openEdit(item)">
            <span class="or-list-card__title">{{ item.name }}</span>
            <span class="key-perms">
              <Chip
                v-for="chip in permissionChips(item.scopes)"
                :key="chip.id"
                :tone="chip.tone"
                size="sm"
              >
                {{ chip.label }}
              </Chip>
            </span>
            <span class="or-list-card__meta">
              <span>
                Last used
                {{ item.last_used_at ? "" : "never" }}
                <TimeAgo v-if="item.last_used_at" :value="item.last_used_at" />
              </span>
              <span class="card-actions" @click.stop>
                <NButton size="small" quaternary @click="openEdit(item)">Edit</NButton>
                <NPopconfirm @positive-click="revoke(item.id)">
                  <template #trigger>
                    <NButton size="small" quaternary type="error">Delete</NButton>
                  </template>
                  Delete “{{ item.name }}”? Apps and assistants using it will stop working.
                </NPopconfirm>
              </span>
            </span>
          </div>
        </template>
      </DataList>
      <p class="or-footer-count">
        {{ rows.length }} key{{ rows.length === 1 ? "" : "s" }}
      </p>
    </template>

    <CreateApiKeyModal
      v-model:show="showEditor"
      :preset="createPreset"
      :editing="editing"
      @created="onKeyCreated"
      @saved="load"
      @removed="load"
    />

    <NModal
      v-model:show="showKeyModal"
      preset="card"
      title="Save your API key"
      class="or-modal"
      :mask-closable="false"
    >
      <NAlert type="warning" :bordered="false">
        Copy this secret now. It is shown only this once. Use it as a Bearer token or in an assistant setup.
      </NAlert>
      <code class="key-display">{{ createdKey }}</code>

      <section v-if="mcpHostConfig" class="setup-block">
        <div class="setup-block__head">
          <div>
            <h3>Assistant setup</h3>
            <p>Paste this into Cursor, Claude, or a similar app. The key is already filled in.</p>
          </div>
          <NButton text type="primary" @click="copyText(mcpHostConfig, 'assistant setup')">
            Copy setup
          </NButton>
        </div>
        <NCode :code="mcpHostConfig" language="json" word-wrap class="setup-code" />
      </section>

      <template #footer>
        <div class="or-modal-footer">
          <NButton @click="showKeyModal = false">Done</NButton>
          <NButton type="primary" @click="copyText(createdKey!, 'API key')">
            <template #icon>
              <NIcon><CopyOutline /></NIcon>
            </template>
            Copy key
          </NButton>
        </div>
      </template>
    </NModal>
  </div>
</template>

<style scoped>
.key-card {
  cursor: pointer;
}

.card-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

:deep(.key-name) {
  font-weight: 600;
}

:deep(.key-perms) {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 6px;
}

:deep(.muted-cell) {
  color: var(--or-text-3, var(--n-text-color-3));
}

:deep(.row-actions) {
  display: flex;
  gap: 4px;
  align-items: center;
}

.key-display {
  display: block;
  margin-top: 12px;
  padding: 12px;
  background: var(--or-surface-sunken, var(--n-code-color));
  border-radius: 8px;
  font-size: 0.8rem;
  word-break: break-all;
}

.setup-block {
  margin-top: 20px;
}

.setup-block__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.setup-block h3 {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
}

.setup-block p {
  margin: 4px 0 0;
  color: var(--or-text-3, var(--n-text-color-3));
  font-size: 0.8125rem;
  line-height: 1.45;
}

.setup-code {
  display: block;
  max-height: 200px;
  overflow: auto;
  font-size: 12px;
  border-radius: 8px;
}
</style>
