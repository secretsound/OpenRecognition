<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  NInput,
  NInputNumber,
  NSwitch,
  NButton,
  NTag,
  NAlert,
  useMessage,
} from "naive-ui";
import { api } from "@/api/client";
import type { IntegrationConnectivityOut, MqttIntegrationOut } from "@/types/api";
import { ApiError } from "@/api/client";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import SegmentedControl from "@/components/kit/SegmentedControl.vue";
import StickySaveBar from "@/components/kit/StickySaveBar.vue";
import { useUnsavedGuard } from "@/composables/useUnsaved";
import "./integration-panel.css";

type Qos = "0" | "1" | "2";

type Draft = {
  enabled: boolean;
  host: string;
  port: number | null;
  topic_prefix: string;
  username: string;
  password: string;
  client_id: string;
  use_tls: boolean;
  tls_insecure: boolean;
  qos: Qos;
  retain: boolean;
};

const message = useMessage();
const loading = ref(true);
const saving = ref(false);
const testing = ref(false);
const server = ref<MqttIntegrationOut | null>(null);
const testResult = ref<IntegrationConnectivityOut | null>(null);
const clearPassword = ref(false);

const emptyDraft = (): Draft => ({
  enabled: false,
  host: "localhost",
  port: 1883,
  topic_prefix: "openrecognition",
  username: "",
  password: "",
  client_id: "openrecognition",
  use_tls: false,
  tls_insecure: false,
  qos: "0",
  retain: true,
});

const draft = ref<Draft>(emptyDraft());

function fromServer(s: MqttIntegrationOut): Draft {
  return {
    enabled: s.enabled,
    host: s.host,
    port: s.port,
    topic_prefix: s.topic_prefix,
    username: s.username ?? "",
    password: "",
    client_id: s.client_id || "openrecognition",
    use_tls: s.use_tls,
    tls_insecure: s.tls_insecure,
    qos: String(s.qos ?? 0) as Qos,
    retain: s.retain !== false,
  };
}

const dirty = computed(() => {
  if (!server.value) return false;
  const s = server.value;
  const d = draft.value;
  return (
    d.enabled !== s.enabled ||
    d.host !== s.host ||
    (d.port ?? 1883) !== s.port ||
    d.topic_prefix !== s.topic_prefix ||
    d.username !== (s.username ?? "") ||
    d.client_id !== (s.client_id || "openrecognition") ||
    d.use_tls !== s.use_tls ||
    d.tls_insecure !== s.tls_insecure ||
    Number(d.qos) !== (s.qos ?? 0) ||
    d.retain !== (s.retain !== false) ||
    d.password !== "" ||
    clearPassword.value
  );
});

useUnsavedGuard(dirty);

const topicExample = computed(() => {
  const p = draft.value.topic_prefix.trim() || "openrecognition";
  return `${p}/person/Alex/state`;
});

const payloadExample = `{
  "label": "Alex",
  "type": "person",
  "confidence": 0.92,
  "modality": "audio"
}`;

const status = computed(() => {
  if (!draft.value.enabled) return { label: "Off", type: "default" as const };
  if (server.value?.connected) return { label: "Connected", type: "success" as const };
  if (server.value?.last_error) return { label: "Not connected", type: "error" as const };
  return { label: "Waiting", type: "warning" as const };
});

function onTls(on: boolean) {
  draft.value.use_tls = on;
  if (on && draft.value.port === 1883) draft.value.port = 8883;
  if (!on && draft.value.port === 8883) draft.value.port = 1883;
}

function resetDraft() {
  if (!server.value) return;
  draft.value = fromServer(server.value);
  clearPassword.value = false;
  testResult.value = null;
}

async function load() {
  loading.value = true;
  try {
    const s = await api<MqttIntegrationOut>("/v1/integrations/mqtt");
    server.value = s;
    draft.value = fromServer(s);
    clearPassword.value = false;
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load MQTT settings");
  } finally {
    loading.value = false;
  }
}

function testPayload() {
  return {
    host: draft.value.host.trim(),
    port: draft.value.port ?? 1883,
    username: draft.value.username.trim(),
    password: draft.value.password || (clearPassword.value ? "" : null),
    client_id: draft.value.client_id.trim() || "openrecognition",
    use_tls: draft.value.use_tls,
    tls_insecure: draft.value.tls_insecure,
  };
}

async function testConnection() {
  testing.value = true;
  testResult.value = null;
  try {
    testResult.value = await api<IntegrationConnectivityOut>("/v1/integrations/mqtt/test", {
      method: "POST",
      json: testPayload(),
    });
  } catch (e) {
    testResult.value = {
      ok: false,
      message: e instanceof ApiError ? e.message : "Failed to test the broker",
      languages: null,
    };
  } finally {
    testing.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const payload: Record<string, unknown> = {
      enabled: draft.value.enabled,
      host: draft.value.host.trim(),
      port: draft.value.port ?? 1883,
      topic_prefix: draft.value.topic_prefix.trim(),
      username: draft.value.username.trim(),
      client_id: draft.value.client_id.trim() || "openrecognition",
      use_tls: draft.value.use_tls,
      tls_insecure: draft.value.tls_insecure,
      qos: Number(draft.value.qos),
      retain: draft.value.retain,
    };
    if (draft.value.password) payload.password = draft.value.password;
    else if (clearPassword.value) payload.password = "";
    server.value = await api<MqttIntegrationOut>("/v1/integrations/mqtt", {
      method: "PATCH",
      json: payload,
    });
    draft.value = fromServer(server.value);
    clearPassword.value = false;
    testResult.value = null;
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
        Publish each match to an MQTT broker. Most Home Assistant and Mosquitto setups need a
        username and password here.
      </p>
    </header>

    <ContentSkeleton v-if="loading" variant="form" />

    <template v-else>
      <div class="conn-status">
        <div>
          <div class="conn-status__title">Publish matches</div>
          <p class="conn-status__hint">
            Turn this on to send a JSON message every time someone or something is recognized.
          </p>
        </div>
        <div class="conn-status__aside">
          <NTag round :bordered="false" :type="status.type">{{ status.label }}</NTag>
          <NSwitch v-model:value="draft.enabled" />
        </div>
      </div>

      <NAlert
        v-if="draft.enabled && server?.last_error"
        type="error"
        :title="server.last_error"
        :bordered="false"
      />

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">Broker</h3>
            <p class="conn-block__desc">The MQTT server that receives each match.</p>
          </div>
        </div>

        <div class="conn-split">
          <div class="conn-field">
            <span class="conn-field__label">Address</span>
            <NInput v-model:value="draft.host" placeholder="mqtt.local" />
          </div>
          <div class="conn-field">
            <span class="conn-field__label">Port</span>
            <NInputNumber
              v-model:value="draft.port"
              :min="1"
              :max="65535"
              style="width: 100%"
            />
          </div>
        </div>

        <div class="conn-switch">
          <div class="conn-switch__copy">
            <span class="conn-switch__label">Use TLS</span>
            <p class="conn-switch__hint">Encrypted connection. Brokers usually listen on 8883.</p>
          </div>
          <NSwitch :value="draft.use_tls" @update:value="onTls" />
        </div>

        <div v-if="draft.use_tls" class="conn-switch">
          <div class="conn-switch__copy">
            <span class="conn-switch__label">Allow insecure certificate</span>
            <p class="conn-switch__hint">
              Turn this on for a local broker with a self-signed certificate.
            </p>
          </div>
          <NSwitch v-model:value="draft.tls_insecure" />
        </div>
      </section>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">Account</h3>
            <p class="conn-block__desc">Leave blank only if the broker allows anonymous clients.</p>
          </div>
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Username</span>
          <NInput
            v-model:value="draft.username"
            placeholder="mqtt-user"
            autocomplete="username"
          />
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Password</span>
          <div class="conn-field__action">
            <NInput
              v-model:value="draft.password"
              class="conn-field__grow"
              type="password"
              show-password-on="click"
              :placeholder="server?.password_set && !clearPassword ? 'Saved — type to replace' : 'Password'"
              autocomplete="new-password"
              :disabled="clearPassword"
            />
            <NButton
              v-if="server?.password_set"
              quaternary
              @click="clearPassword = !clearPassword; draft.password = ''"
            >
              {{ clearPassword ? "Keep saved" : "Remove" }}
            </NButton>
          </div>
          <p v-if="clearPassword" class="conn-field__hint">The saved password will be removed on save.</p>
        </div>
      </section>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">Messages</h3>
            <p class="conn-block__desc">How each match is published on the broker.</p>
          </div>
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Client id</span>
          <p class="conn-field__hint">How this app identifies itself to the broker.</p>
          <NInput v-model:value="draft.client_id" placeholder="openrecognition" />
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Topic prefix</span>
          <p class="conn-field__hint">
            An example is <code>{{ topicExample }}</code>.
          </p>
          <NInput v-model:value="draft.topic_prefix" placeholder="openrecognition" />
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Quality of service</span>
          <p class="conn-field__hint">How hard the broker should try to deliver each message.</p>
          <SegmentedControl
            v-model="draft.qos"
            aria-label="MQTT quality of service"
            :options="[
              { value: '0', label: '0 — at most once' },
              { value: '1', label: '1 — at least once' },
              { value: '2', label: '2 — exactly once' },
            ]"
          />
        </div>

        <div class="conn-switch">
          <div class="conn-switch__copy">
            <span class="conn-switch__label">Keep last message</span>
            <p class="conn-switch__hint">
              New subscribers immediately see the latest match for that person.
            </p>
          </div>
          <NSwitch v-model:value="draft.retain" />
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Example payload</span>
          <pre class="wh-json">{{ payloadExample }}</pre>
        </div>
      </section>

      <div class="int-panel__actions">
        <NButton :loading="testing" @click="testConnection">Test connection</NButton>
      </div>
      <NAlert
        v-if="testResult"
        :type="testResult.ok ? 'success' : 'error'"
        :title="testResult.message"
        :bordered="false"
      />

      <StickySaveBar :dirty="dirty" :saving="saving" @save="save" @discard="resetDraft" />
    </template>
  </div>
</template>
