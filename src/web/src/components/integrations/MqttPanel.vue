<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  NInput,
  NInputNumber,
  NSwitch,
  NButton,
  NSkeleton,
  NTag,
  useMessage,
} from "naive-ui";
import { api } from "@/api/client";
import type { MqttIntegrationOut } from "@/types/api";
import { ApiError } from "@/api/client";
import "./integration-panel.css";

const message = useMessage();
const loading = ref(true);
const saving = ref(false);
const server = ref<MqttIntegrationOut | null>(null);

const draft = ref({
  enabled: false,
  host: "localhost",
  port: 1883,
  topic_prefix: "openrecognition",
});

const dirty = computed(() => {
  if (!server.value) return false;
  const s = server.value;
  return (
    draft.value.enabled !== s.enabled ||
    draft.value.host !== s.host ||
    draft.value.port !== s.port ||
    draft.value.topic_prefix !== s.topic_prefix
  );
});

const topicExample = computed(() => {
  const p = draft.value.topic_prefix.trim() || "openrecognition";
  return `${p}/person/alex/state`;
});

async function load() {
  loading.value = true;
  try {
    const s = await api<MqttIntegrationOut>("/v1/integrations/mqtt");
    server.value = s;
    draft.value = {
      enabled: s.enabled,
      host: s.host,
      port: s.port,
      topic_prefix: s.topic_prefix,
    };
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load MQTT settings");
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    server.value = await api<MqttIntegrationOut>("/v1/integrations/mqtt", {
      method: "PATCH",
      json: {
        enabled: draft.value.enabled,
        host: draft.value.host.trim(),
        port: draft.value.port,
        topic_prefix: draft.value.topic_prefix.trim(),
      },
    });
    draft.value = { ...server.value };
    message.success("MQTT settings saved");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to save");
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="int-panel">
    <header class="int-panel__header">
      <p class="int-panel__lead">
        Each match is published as a message your broker can keep, so other devices can react.
      </p>
      <NButton type="primary" :loading="saving" :disabled="!dirty || loading" @click="save">
        Save
      </NButton>
    </header>

    <NSkeleton v-if="loading" text :repeat="4" />

    <template v-else>
      <div class="conn-status">
        <div>
          <div class="conn-status__title">Publish matches</div>
          <p class="conn-status__hint">Turn this on to send a message every time someone or something is recognized.</p>
        </div>
        <div class="conn-status__aside">
          <NTag round :bordered="false" :type="draft.enabled ? 'success' : 'default'">
            {{ draft.enabled ? "Publishing" : "Off" }}
          </NTag>
          <NSwitch v-model:value="draft.enabled" />
        </div>
      </div>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">Broker</h3>
            <p class="conn-block__desc">The message server that receives each match.</p>
          </div>
        </div>

        <div class="conn-split">
          <div class="conn-field">
            <span class="conn-field__label">Address</span>
            <NInput
              v-model:value="draft.host"
              :disabled="!draft.enabled"
              placeholder="localhost"
            />
          </div>
          <div class="conn-field">
            <span class="conn-field__label">Port</span>
            <NInputNumber
              v-model:value="draft.port"
              :disabled="!draft.enabled"
              :min="1"
              :max="65535"
              style="width: 100%"
            />
          </div>
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Topic</span>
          <p class="conn-field__hint">
            Messages use this prefix. An example is <code>{{ topicExample }}</code>.
          </p>
          <NInput
            v-model:value="draft.topic_prefix"
            :disabled="!draft.enabled"
            placeholder="openrecognition"
          />
        </div>
      </section>
    </template>
  </div>
</template>
