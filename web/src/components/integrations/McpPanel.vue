<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NButton,
  NSkeleton,
  NTag,
  NAlert,
  NCode,
  NIcon,
  useMessage,
} from "naive-ui";
import { CopyOutline } from "@vicons/ionicons5";
import { api } from "@/api/client";
import type { McpIntegrationOut } from "@/types/api";
import { ApiError } from "@/api/client";
import "./integration-panel.css";

const message = useMessage();
const router = useRouter();
const loading = ref(true);
const info = ref<McpIntegrationOut | null>(null);

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

function scopeLabel(scope: string) {
  if (scope === "read") return "View";
  if (scope === "recognize") return "Recognize";
  if (scope === "enroll") return "Add to library";
  if (scope === "admin") return "Admin";
  return scope;
}

async function load() {
  loading.value = true;
  try {
    info.value = await api<McpIntegrationOut>("/v1/integrations/mcp");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load MCP settings");
  } finally {
    loading.value = false;
  }
}

async function copyTemplate() {
  if (!info.value) return;
  try {
    await navigator.clipboard.writeText(info.value.host_config_json);
    message.success("Copied config template");
  } catch {
    message.error("Clipboard unavailable");
  }
}

onMounted(load);
</script>

<template>
  <div class="int-panel">
    <header class="int-panel__header">
      <p class="int-panel__lead">
        Point an assistant such as Claude or Cursor at this server. Create a key under
        <NButton text type="primary" size="tiny" @click="router.push('/keys')">API keys</NButton>
        — that key decides which actions the assistant can use.
      </p>
      <NButton type="primary" :disabled="!info" @click="copyTemplate">
        <template #icon>
          <NIcon :component="CopyOutline" />
        </template>
        Copy setup
      </NButton>
    </header>

    <NSkeleton v-if="loading" text :repeat="6" />

    <template v-else-if="info">
      <div class="conn-status">
        <div>
          <div class="conn-status__title">{{ info.api_base_url }}</div>
          <p class="conn-status__hint">
            This is the address an assistant uses. The API key decides which actions are allowed.
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
            <h3 class="conn-block__title">What an assistant can do</h3>
            <p class="conn-block__desc">Each action needs a matching permission on the API key.</p>
          </div>
        </div>
        <ul class="conn-list">
          <li v-for="tool in info.tools" :key="tool.name" class="conn-list__item">
            <div>
              <div class="conn-list__title">{{ tool.name }}</div>
              <p class="conn-list__desc">
                {{
                  tool.name === "audio_gate"
                    ? "Check whether a clip sounds like speech before matching a person."
                    : tool.description
                }}
              </p>
            </div>
            <NTag round :bordered="false">{{ scopeLabel(tool.scope) }}</NTag>
          </li>
        </ul>
      </section>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">Setup for your assistant</h3>
            <p class="conn-block__desc">
              Paste this into Claude, Cursor, or another assistant. Create the key under API keys, then set
              <code>OPENRECOGNITION_API_KEY</code>.
            </p>
          </div>
        </div>
        <ul class="conn-list">
          <li v-for="hint in info.host_config_hints" :key="hint.host" class="conn-list__item">
            <div>
              <div class="conn-list__title">{{ hint.host }}</div>
              <p class="conn-list__desc"><code>{{ hint.config_path }}</code></p>
            </div>
          </li>
        </ul>
        <NCode class="conn-code" :code="info.host_config_json" language="json" word-wrap />
      </section>
    </template>
  </div>
</template>

