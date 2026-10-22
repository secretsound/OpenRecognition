<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NDataTable,
  NButton,
  NModal,
  NTag,
  NSpace,
  NAlert,
  NPopconfirm,
  NIcon,
  NCode,
  useMessage,
} from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import { AddOutline, TrashOutline, CopyOutline } from "@vicons/ionicons5";
import { api, loadFailureMessage } from "@/api/client";
import type { ApiKeyOut, ApiKeyCreated } from "@/types/api";
import PageHeader from "@/components/kit/PageHeader.vue";
import { formatAbsolute } from "@/utils/time";
import DataList from "@/components/kit/DataList.vue";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import EmptyState from "@/components/EmptyState.vue";
import CreateApiKeyModal from "@/components/CreateApiKeyModal.vue";
import { KeyOutline } from "@vicons/ionicons5";
import { ApiError } from "@/api/client";
import { useMcpCatalog } from "@/composables/useMcpCatalog";

const message = useMessage();
const route = useRoute();
const router = useRouter();
const { catalog, ensureCatalog, hostConfigWithKey } = useMcpCatalog();

const loading = ref(true);
const loadError = ref<string | null>(null);
const rows = ref<ApiKeyOut[]>([]);
const showCreate = ref(false);
const createPreset = ref<"default" | "mcp" | "integration">("default");
const showKeyModal = ref(false);
const createdKey = ref<string | null>(null);
const createdMcpTools = ref<ApiKeyCreated["mcp_tools"]>([]);
const revokingId = ref<string | null>(null);

const showMcpSuccessExtras = computed(
  () => createdMcpTools.value.length > 0 && hostConfigWithKey(createdKey.value ?? ""),
);

const mcpHostConfig = computed(() =>
  createdKey.value ? hostConfigWithKey(createdKey.value) : "",
);

function openCreate(preset: "default" | "mcp" | "integration" = "default") {
  createPreset.value = preset;
  showCreate.value = true;
}

function onKeyCreated(res: ApiKeyCreated) {
  createdKey.value = res.key;
  createdMcpTools.value = res.mcp_tools ?? [];
  showKeyModal.value = true;
  if (route.query.for === "mcp") {
    router.replace({ path: "/keys" });
  }
  void load();
}

const columns: DataTableColumns<ApiKeyOut> = [
  {
    title: "Name",
    key: "name",
    minWidth: 120,
    ellipsis: { tooltip: true },
    sorter: (a, b) => a.name.localeCompare(b.name),
  },
  {
    title: "REST API",
    key: "scopes",
    minWidth: 130,
    render(row) {
      if (!row.scopes?.length) return h("span", { class: "muted-cell" }, "—");
      return h(
        NSpace,
        { size: 4, wrap: true },
        () =>
          row.scopes.map((scope) =>
            h(
              NTag,
              {
                size: "small",
                round: true,
                bordered: false,
                type: scope === "admin" ? "warning" : "default",
              },
              () => scope,
            ),
          ),
      );
    },
  },
  {
    title: "MCP",
    key: "mcp_tool_allowlist",
    minWidth: 160,
    render(row) {
      if (row.mcp_tool_allowlist === null) {
        return h("span", { class: "muted-cell" }, row.scopes?.length ? "All in scope" : "—");
      }
      if (!row.mcp_tool_allowlist.length) {
        return h("span", { class: "muted-cell" }, "—");
      }
      return h(
        NSpace,
        { size: 4, wrap: true },
        () =>
          row.mcp_tool_allowlist!.map((name) =>
            h(NTag, { size: "small", round: true, bordered: false }, () => name),
          ),
      );
    },
  },
  {
    title: "Last used",
    key: "last_used_at",
    width: 168,
    render(row) {
      return row.last_used_at
        ? formatAbsolute(row.last_used_at)
        : h("span", { class: "muted-cell" }, "Never");
    },
  },
  {
    title: "Created",
    key: "created_at",
    width: 168,
    sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    render(row) {
      return formatAbsolute(row.created_at);
    },
  },
  {
    title: "",
    key: "actions",
    width: 52,
    fixed: "right",
    render(row) {
      return h(
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
                "aria-label": "Delete key",
                loading: revokingId.value === row.id,
                onClick: (e: Event) => e.stopPropagation(),
              },
              { icon: () => h(NIcon, null, { default: () => h(TrashOutline) }) },
            ),
          default: () => `Delete API key "${row.name}"? Integrations using it will stop working.`,
        },
      );
    },
  },
];

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
  if (route.query.for === "mcp") {
    openCreate("mcp");
  }
});

watch(
  () => route.query.for,
  (v) => {
    if (v === "mcp" && !showCreate.value) openCreate("mcp");
  },
);
</script>

<template>
  <div class="or-page">
    <PageHeader
      title="API keys"
      description="Keys let other apps call this server. REST is the web API. MCP is the tool list an AI assistant can use."
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
      description="Create a key with REST scopes, MCP tools, or both."
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
            />
          </div>
        </template>
        <template #card="{ item }">
          <div class="or-list-card key-card">
            <span class="or-list-card__title">{{ item.name }}</span>
            <span class="or-list-card__meta">
              <span>
                Last used
                {{ item.last_used_at ? formatAbsolute(item.last_used_at) : "never" }}
              </span>
              <NPopconfirm @positive-click="revoke(item.id)">
                <template #trigger>
                  <NButton size="small" quaternary type="error">Remove</NButton>
                </template>
                Delete API key "{{ item.name }}"? Apps using it will stop working.
              </NPopconfirm>
            </span>
          </div>
        </template>
      </DataList>
      <p class="or-footer-count">
        {{ rows.length }} key{{ rows.length === 1 ? "" : "s" }}
      </p>
    </template>

    <CreateApiKeyModal
      v-model:show="showCreate"
      :catalog="catalog"
      :preset="createPreset"
      @created="onKeyCreated"
    />

    <NModal
      v-model:show="showKeyModal"
      preset="card"
      title="Save your API key"
      class="or-modal"
      :mask-closable="false"
    >
      <NAlert type="warning" :bordered="false">
        This secret is shown once. Copy it before closing.
      </NAlert>

      <code class="key-display">{{ createdKey }}</code>

      <template v-if="showMcpSuccessExtras">
        <p class="mcp-note">
          MCP is the tool list an assistant uses. Paste this host configuration into that assistant.
        </p>
        <NButton text type="primary" @click="copyText(mcpHostConfig, 'MCP host config')">
          Copy assistant configuration
        </NButton>
        <NCode :code="mcpHostConfig" language="json" word-wrap class="mcp-config-code" />
      </template>

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
  cursor: default;
}

:deep(.muted-cell) {
  color: var(--n-text-color-3);
  font-size: 0.8125rem;
}

.key-display {
  display: block;
  margin-top: 12px;
  padding: 12px;
  background: var(--n-code-color);
  border-radius: 8px;
  font-size: 0.8rem;
  word-break: break-all;
}

.mcp-note {
  margin: 16px 0 8px;
  color: var(--n-text-color-3);
  font-size: 0.8125rem;
  line-height: 1.45;
}

.success-mcp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 16px 0 8px;
}

.success-mcp-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--n-text-color-2);
}

.mcp-config-code {
  display: block;
  max-height: 200px;
  overflow: auto;
  font-size: 12px;
  border-radius: 8px;
}
</style>
