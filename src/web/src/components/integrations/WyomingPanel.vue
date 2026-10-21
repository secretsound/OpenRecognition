<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  NInput,
  NSwitch,
  NButton,
  NSkeleton,
  NTag,
  NInputNumber,
  NAlert,
  NSelect,
  useMessage,
} from "naive-ui";
import { api } from "@/api/client";
import type {
  IntegrationConnectivityOut,
  MdnsDiscoveryOut,
  WyomingIntegrationOut,
} from "@/types/api";
import { ApiError } from "@/api/client";
import "./integration-panel.css";

const CUSTOM = "__custom__";

type PanelAlert = {
  id: string;
  type: "error" | "warning" | "info";
  title: string;
  summary?: string;
  details?: string;
};

const message = useMessage();
const loading = ref(true);
const saving = ref(false);
const scanning = ref(false);
const testingHa = ref(false);
const testingUpstream = ref(false);
const haTestResult = ref<IntegrationConnectivityOut | null>(null);
const upstreamTestResult = ref<IntegrationConnectivityOut | null>(null);
const server = ref<WyomingIntegrationOut | null>(null);
const discovery = ref<MdnsDiscoveryOut | null>(null);
const upstreamChoice = ref<string>(CUSTOM);
const homeAssistantChoice = ref<string>(CUSTOM);

const draft = ref({
  enabled: false,
  uri: "tcp://0.0.0.0:10301",
  upstream_uri: "tcp://127.0.0.1:10300",
  home_assistant_url: "" as string,
  min_confidence: 0.75,
  require_speaker_match: true,
  block_on_gate_reject: true,
  tag_speaker: false,
  zeroconf_enabled: true,
  zeroconf_name: "openrecognition",
  advertise_host: "" as string,
});

function tcpPort(uri: string): number | null {
  const match = uri.trim().match(/^tcp:\/\/[^/]*:(\d+)\s*$/i);
  return match ? Number.parseInt(match[1], 10) : null;
}

const portsConflict = computed(() => {
  const listen = tcpPort(draft.value.uri);
  const upstream = tcpPort(draft.value.upstream_uri);
  return listen !== null && upstream !== null && listen === upstream;
});

const listenPort = computed(
  () => server.value?.discovery?.listen_port ?? tcpPort(draft.value.uri) ?? 10301,
);

const upstreamOptions = computed(() => {
  const opts = [{ label: "Type an address", value: CUSTOM }];
  for (const w of discovery.value?.wyoming ?? []) {
    opts.push({ label: `${w.name} — ${w.uri}`, value: w.uri });
  }
  return opts;
});

const homeAssistantOptions = computed(() => {
  const opts = [{ label: "Type an address", value: CUSTOM }];
  for (const h of discovery.value?.home_assistant ?? []) {
    opts.push({ label: `${h.name} — ${h.url}`, value: h.url });
  }
  return opts;
});

const upstreamManual = computed(() => upstreamChoice.value === CUSTOM);
const homeAssistantManual = computed(() => homeAssistantChoice.value === CUSTOM);

const effectiveHaUrl = computed(() => {
  if (homeAssistantChoice.value !== CUSTOM) return homeAssistantChoice.value;
  return draft.value.home_assistant_url.trim();
});

const effectiveUpstreamUri = computed(() => {
  if (upstreamChoice.value !== CUSTOM) return upstreamChoice.value;
  return draft.value.upstream_uri.trim();
});

const dirty = computed(() => {
  if (!server.value) return false;
  const s = server.value;
  const ha = draft.value.home_assistant_url.trim() || null;
  const savedHa = s.home_assistant_url?.trim() || null;
  return (
    draft.value.enabled !== s.enabled ||
    draft.value.uri !== s.uri ||
    draft.value.upstream_uri !== s.upstream_uri ||
    ha !== savedHa ||
    draft.value.min_confidence !== s.min_confidence ||
    draft.value.require_speaker_match !== s.require_speaker_match ||
    draft.value.block_on_gate_reject !== s.block_on_gate_reject ||
    draft.value.tag_speaker !== s.tag_speaker ||
    draft.value.zeroconf_enabled !== s.zeroconf_enabled ||
    draft.value.zeroconf_name !== s.zeroconf_name ||
    (draft.value.advertise_host.trim() || null) !== (s.advertise_host?.trim() || null)
  );
});

const panelAlerts = computed((): PanelAlert[] => {
  const s = server.value;
  if (!s) return [];
  const out: PanelAlert[] = [];

  if (!s.available) {
    out.push({
      id: "pkg",
      type: "warning",
      title: "This connection is not installed",
      summary: "Reinstall OpenRecognition with Wyoming support, then restart the server.",
    });
  }
  if (portsConflict.value || s.ports_conflict) {
    const port = tcpPort(draft.value.uri);
    out.push({
      id: "ports",
      type: "error",
      title: "Those two addresses use the same port",
      summary: `Both use port ${port}. Home Assistant should connect to a different port, such as 10301.`,
    });
  }
  if (s.listen_error) {
    out.push({
      id: "listen",
      type: "error",
      title: "Listener failed to start",
      summary: s.listen_error,
    });
  }
  if (draft.value.enabled && !s.upstream_ready && !portsConflict.value) {
    const testedUri = effectiveUpstreamUri.value;
    const recentlyTestedOk =
      upstreamTestResult.value?.ok === true && testedUri === draft.value.upstream_uri.trim();
    if (!recentlyTestedOk) {
      out.push({
        id: "upstream",
        type: "warning",
      title: "The speech-to-text service is not answering",
      summary: `Nothing is answering at ${draft.value.upstream_uri}. Start that service, or pick one found on your network.`,
      });
    }
  }
  if (s.discovery?.mdns_likely_limited) {
    out.push({
      id: "container",
      type: "warning",
      title: "Home Assistant will not find this server automatically",
      summary: "This server is running in a container, so other devices may not see it on their own.",
      details: `In Home Assistant, add the Wyoming integration with this computer's network address and port ${listenPort.value}. If this server runs in Docker, publish port ${listenPort.value}.`,
    });
  } else if (draft.value.enabled && draft.value.zeroconf_enabled && !s.zeroconf_registered) {
    out.push({
      id: "mdns",
      type: "info",
      title: "This server is not showing up on the network yet",
      summary:
        "Add it in Home Assistant with this computer's address and listen port, or set the address to advertise below.",
    });
  }
  return out;
});

function syncChoicesFromDraft() {
  const up = discovery.value?.wyoming.find((w) => w.uri === draft.value.upstream_uri);
  upstreamChoice.value = up?.uri ?? CUSTOM;
  const haUrl = draft.value.home_assistant_url.trim();
  const ha = discovery.value?.home_assistant.find((h) => h.url === haUrl);
  homeAssistantChoice.value = ha?.url ?? CUSTOM;
}

watch(upstreamChoice, (value) => {
  if (value !== CUSTOM) draft.value.upstream_uri = value;
  upstreamTestResult.value = null;
});

watch(homeAssistantChoice, (value) => {
  if (value !== CUSTOM) draft.value.home_assistant_url = value;
  haTestResult.value = null;
});

watch(
  () => draft.value.home_assistant_url,
  () => {
    haTestResult.value = null;
  },
);

watch(
  () => draft.value.upstream_uri,
  () => {
    upstreamTestResult.value = null;
  },
);

async function scanNetwork() {
  scanning.value = true;
  try {
    discovery.value = await api<MdnsDiscoveryOut>("/v1/integrations/discover?timeout=4");
    syncChoicesFromDraft();
    if (!discovery.value.available) {
      message.warning(
        "mDNS browse unavailable — install pip install 'openrecognition[wyoming]' on the server",
      );
    }
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Network scan failed");
  } finally {
    scanning.value = false;
  }
}

async function testHomeAssistant() {
  const url = effectiveHaUrl.value;
  if (!url) {
    message.warning("Enter or select a Home Assistant URL first");
    return;
  }
  testingHa.value = true;
  haTestResult.value = null;
  try {
    haTestResult.value = await api<IntegrationConnectivityOut>(
      "/v1/integrations/wyoming/test-home-assistant",
      { method: "POST", json: { url } },
    );
    if (haTestResult.value.ok) message.success(haTestResult.value.message);
    else message.error(haTestResult.value.message);
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Home Assistant test failed");
  } finally {
    testingHa.value = false;
  }
}

async function testUpstream() {
  const uri = effectiveUpstreamUri.value;
  if (!uri) {
    message.warning("Enter or select an upstream STT URI first");
    return;
  }
  testingUpstream.value = true;
  upstreamTestResult.value = null;
  try {
    upstreamTestResult.value = await api<IntegrationConnectivityOut>(
      "/v1/integrations/wyoming/test-upstream",
      { method: "POST", json: { uri } },
    );
    if (upstreamTestResult.value.ok) message.success(upstreamTestResult.value.message);
    else message.error(upstreamTestResult.value.message);
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Upstream STT test failed");
  } finally {
    testingUpstream.value = false;
  }
}

async function load() {
  loading.value = true;
  try {
    const s = await api<WyomingIntegrationOut>("/v1/integrations/wyoming");
    server.value = s;
    draft.value = {
      enabled: s.enabled,
      uri: s.uri,
      upstream_uri: s.upstream_uri,
      home_assistant_url: s.home_assistant_url ?? "",
      min_confidence: s.min_confidence,
      require_speaker_match: s.require_speaker_match,
      block_on_gate_reject: s.block_on_gate_reject,
      tag_speaker: s.tag_speaker,
      zeroconf_enabled: s.zeroconf_enabled,
      zeroconf_name: s.zeroconf_name,
      advertise_host: s.advertise_host ?? "",
    };
    syncChoicesFromDraft();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load Wyoming settings");
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const ha = draft.value.home_assistant_url.trim();
    server.value = await api<WyomingIntegrationOut>("/v1/integrations/wyoming", {
      method: "PATCH",
      json: {
        ...draft.value,
        home_assistant_url: ha || null,
        advertise_host: draft.value.advertise_host.trim() || null,
      },
    });
    draft.value = {
      enabled: server.value.enabled,
      uri: server.value.uri,
      upstream_uri: server.value.upstream_uri,
      home_assistant_url: server.value.home_assistant_url ?? "",
      min_confidence: server.value.min_confidence,
      require_speaker_match: server.value.require_speaker_match,
      block_on_gate_reject: server.value.block_on_gate_reject,
      tag_speaker: server.value.tag_speaker,
      zeroconf_enabled: server.value.zeroconf_enabled,
      zeroconf_name: server.value.zeroconf_name,
      advertise_host: server.value.advertise_host ?? "",
    };
    syncChoicesFromDraft();
    if (server.value.upstream_ready) upstreamTestResult.value = null;
    message.success("Wyoming settings saved");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to save");
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await Promise.all([load(), scanNetwork()]);
});
</script>

<template>
  <div class="int-panel">
    <header class="int-panel__header">
      <p class="int-panel__lead">
        Home Assistant connects here to hear who is speaking. A match runs first, then the audio
        goes on to your speech-to-text service.
      </p>
      <div class="int-panel__actions">
        <NButton quaternary :disabled="loading" @click="load">Reload</NButton>
        <NButton type="primary" :loading="saving" :disabled="!dirty || loading" @click="save">
          Save
        </NButton>
      </div>
    </header>

    <NSkeleton v-if="loading" text :repeat="8" />

    <template v-else>
      <div class="conn-status">
        <div>
          <div class="conn-status__title">Accept connections from Home Assistant</div>
          <p class="conn-status__hint">
            Turn this on after the addresses below look right.
            <template v-if="discovery?.available === false">
              Scanning the network is not available on this server.
            </template>
          </p>
        </div>
        <div class="conn-status__aside">
          <NTag
            v-if="draft.enabled"
            round
            :bordered="false"
            :type="server?.listen_error ? 'error' : server?.upstream_ready ? 'success' : 'warning'"
          >
            {{
              server?.listen_error
                ? "Needs attention"
                : server?.upstream_ready
                  ? "Listening"
                  : "Waiting for speech-to-text"
            }}
          </NTag>
          <NTag v-else round :bordered="false">Off</NTag>
          <NSwitch v-model:value="draft.enabled" />
        </div>
      </div>

      <NAlert
        v-for="alert in panelAlerts"
        :key="alert.id"
        :type="alert.type"
        :title="alert.title"
        :bordered="false"
      >
        <p v-if="alert.summary" class="conn-field__hint">{{ alert.summary }}</p>
        <p v-if="alert.details" class="conn-field__hint">{{ alert.details }}</p>
      </NAlert>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">Addresses</h3>
            <p class="conn-block__desc">Where Home Assistant connects, and where words are transcribed.</p>
          </div>
          <NButton :loading="scanning" @click="scanNetwork">Scan the network</NButton>
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Address Home Assistant uses</span>
          <p class="conn-field__hint">Use a different port from the speech-to-text service.</p>
          <NInput v-model:value="draft.uri" placeholder="tcp://0.0.0.0:10301" />
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Speech-to-text service</span>
          <p class="conn-field__hint">
            This turns the audio into words after someone is recognized. Faster Whisper is a common choice.
          </p>
          <NSelect
            v-if="upstreamOptions.length > 1"
            v-model:value="upstreamChoice"
            :options="upstreamOptions"
            :loading="scanning"
            filterable
            placeholder="Choose a service, or type an address"
          />
          <div class="conn-field__action">
            <NInput
              v-if="upstreamManual"
              v-model:value="draft.upstream_uri"
              class="conn-field__grow"
              placeholder="tcp://127.0.0.1:10300"
            />
            <NInput v-else class="conn-field__grow" :value="effectiveUpstreamUri" disabled />
            <NButton
              :loading="testingUpstream"
              :disabled="!effectiveUpstreamUri"
              @click="testUpstream"
            >
              Test
            </NButton>
            <NTag
              v-if="upstreamTestResult"
              round
              :bordered="false"
              :type="upstreamTestResult.ok ? 'success' : 'warning'"
            >
              {{ upstreamTestResult.ok ? "Reachable" : "Not reachable" }}
            </NTag>
          </div>
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Home Assistant address</span>
          <p class="conn-field__hint">Optional. Used only to check that this server can reach Home Assistant.</p>
          <NSelect
            v-if="homeAssistantOptions.length > 1"
            v-model:value="homeAssistantChoice"
            :options="homeAssistantOptions"
            :loading="scanning"
            filterable
            placeholder="Choose Home Assistant, or type an address"
          />
          <div class="conn-field__action">
            <NInput
              v-if="homeAssistantManual"
              v-model:value="draft.home_assistant_url"
              class="conn-field__grow"
              placeholder="http://homeassistant.local:8123"
            />
            <NInput v-else class="conn-field__grow" :value="effectiveHaUrl" disabled />
            <NButton :loading="testingHa" :disabled="!effectiveHaUrl" @click="testHomeAssistant">
              Test
            </NButton>
            <NTag
              v-if="haTestResult"
              round
              :bordered="false"
              :type="haTestResult.ok ? 'success' : 'warning'"
            >
              {{ haTestResult.ok ? "Reachable" : "Not reachable" }}
            </NTag>
          </div>
        </div>
      </section>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">When someone speaks</h3>
            <p class="conn-block__desc">How sure a match must be, and what happens next.</p>
          </div>
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Minimum confidence</span>
          <p class="conn-field__hint">From 0 to 1. A higher number means the match must be more certain.</p>
          <NInputNumber
            v-model:value="draft.min_confidence"
            :min="0"
            :max="1"
            :step="0.05"
            style="width: 160px"
          />
        </div>

        <div class="conn-switch">
          <div class="conn-switch__copy">
            <span class="conn-switch__label">Only continue when someone is recognized</span>
            <p class="conn-switch__hint">
              Unknown voices are not sent on for transcription. Turn this off to transcribe anyway.
            </p>
          </div>
          <NSwitch v-model:value="draft.require_speaker_match" />
        </div>

        <div class="conn-switch">
          <div class="conn-switch__copy">
            <span class="conn-switch__label">Ignore clips that are not speech</span>
            <p class="conn-switch__hint">
              Television, music, and background noise stay out of the transcript.
            </p>
          </div>
          <NSwitch v-model:value="draft.block_on_gate_reject" />
        </div>

        <div class="conn-switch">
          <div class="conn-switch__copy">
            <span class="conn-switch__label">Add the person's name to the transcript</span>
            <p class="conn-switch__hint">
              A recognized person is added in front of the words, like [speaker: Luke].
              Assist sends that whole line to the conversation agent.
            </p>
          </div>
          <NSwitch v-model:value="draft.tag_speaker" />
        </div>
      </section>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">Show this server on your network</h3>
            <p class="conn-block__desc">
              Home Assistant can find it on its own. You can still add the address by hand.
            </p>
          </div>
        </div>

        <div class="conn-switch">
          <div class="conn-switch__copy">
            <span class="conn-switch__label">Announce on the local network</span>
            <p class="conn-switch__hint">Home Assistant can discover this server without a typed address.</p>
          </div>
          <NSwitch v-model:value="draft.zeroconf_enabled" />
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Name on the network</span>
          <NInput
            v-model:value="draft.zeroconf_name"
            placeholder="openrecognition"
            :disabled="!draft.zeroconf_enabled"
          />
        </div>

        <div class="conn-field">
          <span class="conn-field__label">Address to announce</span>
          <p class="conn-field__hint">
            Use this computer's address on your network when the server runs in Docker. Leave blank to choose automatically.
          </p>
          <NInput
            v-model:value="draft.advertise_host"
            placeholder="192.168.1.10"
            :disabled="!draft.zeroconf_enabled"
          />
        </div>
      </section>
    </template>
  </div>
</template>
