<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  NButton,
  NInput,
  NTag,
  NAlert,
  NCode,
  NIcon,
  useMessage,
} from "naive-ui";
import { CopyOutline, KeyOutline } from "@vicons/ionicons5";
import { api } from "@/api/client";
import type { ApiKeyCreated, McpIntegrationOut, McpToolOut } from "@/types/api";
import { ApiError } from "@/api/client";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import SegmentedControl from "@/components/kit/SegmentedControl.vue";
import CreateApiKeyModal from "@/components/CreateApiKeyModal.vue";
import "./integration-panel.css";

type HostId = "cursor" | "claude" | "vscode" | "other";

const HOSTS: { id: HostId; label: string; path: string; hint: string }[] = [
  {
    id: "cursor",
    label: "Cursor",
    path: "~/.cursor/mcp.json or .cursor/mcp.json in the project",
    hint: "Cursor → Settings → MCP, or drop the file in the project.",
  },
  {
    id: "claude",
    label: "Claude",
    path: "claude_desktop_config.json (Application Support/Claude on macOS, %APPDATA%\\Claude on Windows)",
    hint: "Quit Claude Desktop after you save the file, then open it again.",
  },
  {
    id: "vscode",
    label: "VS Code",
    path: ".vscode/mcp.json in the workspace",
    hint: "VS Code uses a servers block instead of mcpServers.",
  },
  {
    id: "other",
    label: "Other",
    path: "Your assistant's MCP server settings",
    hint: "Any client that can run a local command as an MCP server.",
  },
];

const CAPABILITIES: Record<string, { label: string; hint: string; actions: Record<string, string> }> = {
  read: {
    label: "View",
    hint: "Look through the library and see whether the server is ready.",
    actions: {
      get_health: "See if this server is ready.",
      get_capabilities: "See which kinds of recognition are turned on.",
      list_enrollments: "See people, pets, objects, and sounds in the library.",
      get_presence: "See who was recognized recently.",
    },
  },
  recognize: {
    label: "Recognize",
    hint: "Match a voice or a photo.",
    actions: {
      audio_gate: "Tell speech apart from other noise.",
      recognize_audio: "Recognize who is speaking.",
      recognize_image: "Recognize a face, pet, or object in a picture.",
      recognize_image_url: "Recognize a picture from a link, such as a camera snapshot.",
    },
  },
  enroll: {
    label: "Add",
    hint: "Create a profile from files already on this server.",
    actions: {
      enroll_from_paths: "Add a person from photos or audio stored here.",
    },
  },
};

const message = useMessage();
const loading = ref(true);
const info = ref<McpIntegrationOut | null>(null);
const host = ref<HostId>("cursor");
const apiUrl = ref("");
const showCreateKey = ref(false);
const createdKey = ref<string | null>(null);

const selectedHost = computed(() => HOSTS.find((item) => item.id === host.value) ?? HOSTS[0]);

const serverBlock = computed(() => ({
  command: "openrecognition",
  args: ["mcp"],
  env: {
    OPENRECOGNITION_API_URL: apiUrl.value.trim() || "http://127.0.0.1:8080",
    OPENRECOGNITION_API_KEY: createdKey.value || "<api-key>",
  },
}));

const configJson = computed(() => {
  const server = serverBlock.value;
  const doc =
    host.value === "vscode"
      ? { servers: { openrecognition: server } }
      : { mcpServers: { openrecognition: server } };
  return JSON.stringify(doc, null, 2);
});

const capabilityGroups = computed(() => {
  const tools = info.value?.tools ?? [];
  const byScope: Record<string, McpToolOut[]> = {};
  for (const tool of tools) {
    (byScope[tool.scope] ??= []).push(tool);
  }
  return ["read", "recognize", "enroll"]
    .filter((scope) => byScope[scope]?.length && CAPABILITIES[scope])
    .map((scope) => {
      const capability = CAPABILITIES[scope]!;
      return {
        scope,
        label: capability.label,
        hint: capability.hint,
        actions: byScope[scope]!.map((tool) => ({
          name: tool.name,
          label: capability.actions[tool.name] ?? tool.description,
        })),
      };
    });
});

const readyTag = computed(() => {
  if (!info.value) return null;
  return info.value.server_ready
    ? { type: "success" as const, label: "Models ready" }
    : { type: "warning" as const, label: "Models still loading" };
});

const mcpMissing = computed(() => Boolean(info.value && !info.value.available));

async function load() {
  loading.value = true;
  try {
    info.value = await api<McpIntegrationOut>("/v1/integrations/mcp");
    if (!apiUrl.value) apiUrl.value = info.value.api_base_url;
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load MCP settings");
  } finally {
    loading.value = false;
  }
}

async function copyConfig() {
  try {
    await navigator.clipboard.writeText(configJson.value);
    message.success("Copied setup");
  } catch {
    message.error("Clipboard unavailable");
  }
}

function onKeyCreated(payload: ApiKeyCreated) {
  createdKey.value = payload.key;
  message.success("Key created — it is already in the setup below");
}

onMounted(load);
</script>

<template>
  <div class="int-panel">
    <header class="int-panel__header">
      <p class="int-panel__lead">
        Let Cursor, Claude, or another assistant look people up and run a match.
        Create a key, copy the setup, and paste it into that assistant.
      </p>
    </header>

    <ContentSkeleton v-if="loading" variant="form" />

    <template v-else-if="info">
      <div class="conn-status">
        <div>
          <div class="conn-status__title">Assistant access</div>
          <p class="conn-status__hint">
            The assistant calls this server with the key. Restart the assistant after you paste the setup.
          </p>
        </div>
        <div class="conn-status__aside">
          <NTag v-if="readyTag" :type="readyTag.type" round :bordered="false">
            {{ readyTag.label }}
          </NTag>
          <NTag v-if="mcpMissing" type="warning" round :bordered="false">
            Assistant support missing
          </NTag>
        </div>
      </div>

      <NAlert v-if="!info.server_ready" type="info" title="Models are still loading" :bordered="false">
        Recognition waits until the models are ready. Check Models if this stays on.
      </NAlert>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">What the assistant can do</h3>
            <p class="conn-block__desc">
              The key you create turns these on. View and Recognize cover a typical assistant.
              Add lets it create profiles.
            </p>
          </div>
        </div>
        <div class="mcp-caps">
          <article v-for="group in capabilityGroups" :key="group.scope" class="mcp-cap">
            <h4 class="mcp-cap__title">{{ group.label }}</h4>
            <p class="mcp-cap__hint">{{ group.hint }}</p>
            <ul>
              <li v-for="action in group.actions" :key="action.name">{{ action.label }}</li>
            </ul>
          </article>
        </div>
      </section>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">1. Create an API key</h3>
            <p class="conn-block__desc">
              View and Recognize are enough for most assistants. Turn on Add only if it should create profiles.
            </p>
          </div>
          <NButton type="primary" @click="showCreateKey = true">
            <template #icon>
              <NIcon :component="KeyOutline" />
            </template>
            Create key
          </NButton>
        </div>
        <NAlert
          v-if="createdKey"
          type="warning"
          title="This key is shown once"
          :bordered="false"
        >
          It is already filled into the setup below. Copy the setup before you leave this page.
        </NAlert>
      </section>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">2. Paste setup into your assistant</h3>
            <p class="conn-block__desc">{{ selectedHost.hint }}</p>
          </div>
          <NButton @click="copyConfig">
            <template #icon>
              <NIcon :component="CopyOutline" />
            </template>
            Copy setup
          </NButton>
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Assistant</span>
          <SegmentedControl
            v-model="host"
            aria-label="Assistant"
            :options="HOSTS.map((item) => ({ value: item.id, label: item.label }))"
          />
          <p class="conn-field__hint">Put the file at <code>{{ selectedHost.path }}</code>.</p>
        </div>

        <div class="conn-field">
          <span class="conn-field__label">This server's address</span>
          <p class="conn-field__hint">
            Use <code>127.0.0.1</code> if the assistant runs on this computer. Use a LAN address
            if it runs on another machine.
          </p>
          <NInput v-model:value="apiUrl" placeholder="http://127.0.0.1:8080" />
        </div>

        <div class="mcp-setup">
          <span class="conn-field__label">Setup to paste</span>
          <NCode class="conn-code" :code="configJson" language="json" word-wrap />
        </div>
      </section>

      <CreateApiKeyModal
        v-model:show="showCreateKey"
        preset="mcp"
        @created="onKeyCreated"
      />
    </template>
  </div>
</template>

<style scoped>
.mcp-caps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 12px 0 16px;
}

.mcp-cap {
  min-width: 0;
  padding: 16px 16px 8px;
  border-radius: var(--or-radius);
  background: var(--or-surface-2, var(--n-color-embedded, rgba(127, 127, 127, 0.08)));
}

.mcp-cap__title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 650;
}

.mcp-cap__hint {
  margin: 6px 0 0;
  font-size: 0.8125rem;
  line-height: 1.45;
  color: var(--n-text-color-3);
}

.mcp-cap ul {
  margin: 12px 0 0;
  padding: 0 0 8px 1.1rem;
}

.mcp-cap li {
  margin: 0;
  padding: 4px 0;
  font-size: 0.875rem;
  line-height: 1.45;
  color: var(--n-text-color-2);
}

.mcp-setup {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0 8px;
}

@media (max-width: 900px) {
  .mcp-caps {
    grid-template-columns: 1fr;
  }
}
</style>
