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

const TOOL_TITLES: Record<string, string> = {
  get_health: "Server status",
  get_capabilities: "What this server can do",
  list_enrollments: "Library",
  get_presence: "Who was seen recently",
  audio_gate: "Check if a clip is speech",
  recognize_audio: "Match a voice",
  recognize_image: "Match a photo",
  recognize_image_url: "Match a photo from a link",
  enroll_from_paths: "Add someone from files on this server",
};

const SCOPE_TITLES: Record<string, string> = {
  read: "View",
  recognize: "Recognize",
  enroll: "Add to library",
  admin: "Admin",
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

const toolGroups = computed(() => {
  const tools = info.value?.tools ?? [];
  const groups: Record<string, McpToolOut[]> = {};
  for (const tool of tools) {
    (groups[tool.scope] ??= []).push(tool);
  }
  return ["read", "recognize", "enroll"]
    .filter((scope) => groups[scope]?.length)
    .map((scope) => ({
      scope,
      label: SCOPE_TITLES[scope] ?? scope,
      tools: groups[scope]!,
    }));
});

const readyTag = computed(() => {
  if (!info.value) return null;
  return info.value.server_ready
    ? { type: "success" as const, label: "Models ready" }
    : { type: "warning" as const, label: "Models still loading" };
});

const mcpTag = computed(() => {
  if (!info.value) return null;
  return info.value.available
    ? { type: "success" as const, label: "Assistant tools installed" }
    : { type: "warning" as const, label: "Assistant tools not installed" };
});

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
        An assistant such as Cursor or Claude can call this server. It runs
        <code>openrecognition mcp</code> on the computer with the assistant, and talks to
        OpenRecognition with an API key.
      </p>
    </header>

    <ContentSkeleton v-if="loading" variant="form" />

    <template v-else-if="info">
      <div class="conn-status">
        <div>
          <div class="conn-status__title">Assistant access</div>
          <p class="conn-status__hint">
            Create a key, paste the setup into your assistant, then restart that assistant.
          </p>
        </div>
        <div class="conn-status__aside">
          <NTag v-if="readyTag" :type="readyTag.type" round :bordered="false">
            {{ readyTag.label }}
          </NTag>
          <NTag v-if="mcpTag" :type="mcpTag.type" round :bordered="false">
            {{ mcpTag.label }}
          </NTag>
        </div>
      </div>

      <NAlert v-if="info.install_hint" type="warning" title="Install assistant support" :bordered="false">
        On the computer that runs the assistant, install
        <code>{{ info.install_hint }}</code>
      </NAlert>

      <NAlert v-if="!info.server_ready" type="info" title="Models are still loading" :bordered="false">
        Recognition waits until the models are ready. Check Models if this stays on.
      </NAlert>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">1. Create an API key</h3>
            <p class="conn-block__desc">
              A typical assistant needs View and Recognize. Add “Add to library” only if it should
              enroll people.
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

        <NCode class="conn-code" :code="configJson" language="json" word-wrap />
      </section>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">What the assistant can do</h3>
            <p class="conn-block__desc">
              The API key decides which of these tools are allowed.
            </p>
          </div>
        </div>
        <div v-for="group in toolGroups" :key="group.scope" class="mcp-group">
          <h4 class="mcp-group__title">{{ group.label }}</h4>
          <ul class="conn-list">
            <li v-for="tool in group.tools" :key="tool.name" class="conn-list__item">
              <div>
                <div class="conn-list__title">{{ TOOL_TITLES[tool.name] ?? tool.name }}</div>
                <p class="conn-list__desc">{{ tool.description }}</p>
              </div>
            </li>
          </ul>
        </div>
      </section>

      <CreateApiKeyModal
        v-model:show="showCreateKey"
        :catalog="info"
        preset="mcp"
        @created="onKeyCreated"
      />
    </template>
  </div>
</template>
