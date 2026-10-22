<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  NInput,
  NSwitch,
  NButton,
  NTag,
  NInputNumber,
  NAlert,
  NSelect,
  NIcon,
  useMessage,
} from "naive-ui";
import { CopyOutline } from "@vicons/ionicons5";
import { api } from "@/api/client";
import type {
  IntegrationConnectivityOut,
  MdnsDiscoveryOut,
  WyomingIntegrationOut,
} from "@/types/api";
import { ApiError } from "@/api/client";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import StickySaveBar from "@/components/kit/StickySaveBar.vue";
import { useUnsavedGuard } from "@/composables/useUnsaved";
import "./integration-panel.css";

const CUSTOM = "__custom__";

type PanelAlert = {
  id: string;
  type: "error" | "warning" | "info";
  title: string;
  summary?: string;
  details?: string;
};

type Draft = {
  enabled: boolean;
  listenHost: string;
  listenPort: number | null;
  sttHost: string;
  sttPort: number | null;
  home_assistant_url: string;
  require_speaker_match: boolean;
  block_on_gate_reject: boolean;
  tag_speaker: boolean;
  include_confidence: boolean;
  include_candidates: boolean;
  zeroconf_enabled: boolean;
  zeroconf_name: string;
  advertise_host: string;
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

function parseTcp(uri: string, fallbackHost: string, fallbackPort: number) {
  const match = uri.trim().match(/^tcp:\/\/(.+):(\d+)\s*$/i);
  if (!match) return { host: fallbackHost, port: fallbackPort };
  return { host: match[1], port: Number.parseInt(match[2], 10) };
}

function formatTcp(host: string, port: number | null, fallbackPort: number) {
  return `tcp://${(host.trim() || "127.0.0.1")}:${port ?? fallbackPort}`;
}

const draft = ref<Draft>({
  enabled: false,
  listenHost: "0.0.0.0",
  listenPort: 10301,
  sttHost: "127.0.0.1",
  sttPort: 10300,
  home_assistant_url: "",
  require_speaker_match: false,
  block_on_gate_reject: false,
  tag_speaker: true,
  include_confidence: true,
  include_candidates: false,
  zeroconf_enabled: true,
  zeroconf_name: "openrecognition",
  advertise_host: "",
});

const listenUri = computed(() => formatTcp(draft.value.listenHost, draft.value.listenPort, 10301));
const upstreamUri = computed(() => formatTcp(draft.value.sttHost, draft.value.sttPort, 10300));

const portsConflict = computed(() => {
  const listen = draft.value.listenPort ?? 10301;
  const stt = draft.value.sttPort ?? 10300;
  return listen === stt;
});

const listenPort = computed(
  () => server.value?.discovery?.listen_port ?? draft.value.listenPort ?? 10301,
);

const SAMPLE_SPEAKERS = [
  { label: "Luke", confidence: 0.92 },
  { label: "Ada", confidence: 0.41 },
  { label: "Sam", confidence: 0.22 },
];

const transcriptExample = computed(() => {
  const showName = draft.value.tag_speaker;
  const showConfidence = draft.value.include_confidence;
  const showCandidates = draft.value.include_candidates;
  const body = "turn on the kitchen lights";
  if (!showName && !showConfidence && !showCandidates) return body;

  let rows: string[];
  if (showCandidates) {
    rows = SAMPLE_SPEAKERS.map((item) =>
      showConfidence ? `${item.label}: ${Math.round(item.confidence * 100)}%` : item.label,
    );
  } else if (showName) {
    rows = [showConfidence ? "Luke: 92%" : "Luke"];
  } else {
    rows = ["92%"];
  }

  const named = showCandidates || showName;
  const title = named && showConfidence
    ? "[speaker|confidence]"
    : named
      ? "[speaker]"
      : "[confidence]";
  return `${title}\n${rows.join("\n")}\n\n[transcript]\n${body}`;
});

const haConnectHost = computed(() => {
  const advertised = draft.value.advertise_host.trim();
  if (advertised) return advertised;
  return server.value?.discovery?.detected_host || "this-computer";
});

const upstreamOptions = computed(() => {
  const opts = [{ label: "Type an address", value: CUSTOM }];
  for (const w of discovery.value?.wyoming ?? []) {
    opts.push({ label: `${w.name} — ${w.host}:${w.port}`, value: w.uri });
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

const dirty = computed(() => {
  if (!server.value) return false;
  const s = server.value;
  const ha = draft.value.home_assistant_url.trim() || null;
  const savedHa = s.home_assistant_url?.trim() || null;
  return (
    draft.value.enabled !== s.enabled ||
    listenUri.value !== s.uri ||
    upstreamUri.value !== s.upstream_uri ||
    ha !== savedHa ||
    draft.value.require_speaker_match !== s.require_speaker_match ||
    draft.value.block_on_gate_reject !== s.block_on_gate_reject ||
    draft.value.tag_speaker !== s.tag_speaker ||
    draft.value.include_confidence !== s.include_confidence ||
    draft.value.include_candidates !== s.include_candidates ||
    draft.value.zeroconf_enabled !== s.zeroconf_enabled ||
    draft.value.zeroconf_name !== s.zeroconf_name ||
    (draft.value.advertise_host.trim() || null) !== (s.advertise_host?.trim() || null)
  );
});

useUnsavedGuard(dirty);

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
    out.push({
      id: "ports",
      type: "error",
      title: "Those two services use the same port",
      summary: `Both use port ${draft.value.listenPort ?? 10301}. Home Assistant should connect to a different port, such as 10301.`,
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
    const recentlyTestedOk = upstreamTestResult.value?.ok === true;
    if (!recentlyTestedOk) {
      out.push({
        id: "upstream",
        type: "warning",
        title: "The speech-to-text service is not answering",
        summary: `Nothing is answering at ${draft.value.sttHost}:${draft.value.sttPort}. Start Faster Whisper or another Wyoming STT, or pick one found on your network.`,
      });
    }
  }
  if (s.discovery?.mdns_likely_limited) {
    out.push({
      id: "container",
      type: "warning",
      title: "Home Assistant will not find this server automatically",
      summary: "This server is running in a container, so other devices may not see it on their own.",
      details: `In Home Assistant, add Wyoming Protocol with host ${haConnectHost.value} and port ${listenPort.value}. Publish that port on Docker if needed.`,
    });
  } else if (draft.value.enabled && draft.value.zeroconf_enabled && !s.zeroconf_registered) {
    out.push({
      id: "mdns",
      type: "info",
      title: "This server is not showing up on the network yet",
      summary: `Add it in Home Assistant with host ${haConnectHost.value} and port ${listenPort.value}, or set the address to announce below.`,
    });
  }
  return out;
});

function syncChoicesFromDraft() {
  const up = discovery.value?.wyoming.find((w) => w.uri === upstreamUri.value);
  upstreamChoice.value = up?.uri ?? CUSTOM;
  const haUrl = draft.value.home_assistant_url.trim();
  const ha = discovery.value?.home_assistant.find((h) => h.url === haUrl);
  homeAssistantChoice.value = ha?.url ?? CUSTOM;
}

watch(upstreamChoice, (value) => {
  if (value !== CUSTOM) {
    const parsed = parseTcp(value, draft.value.sttHost, draft.value.sttPort ?? 10300);
    draft.value.sttHost = parsed.host;
    draft.value.sttPort = parsed.port;
  }
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

watch(upstreamUri, () => {
  upstreamTestResult.value = null;
});

async function copyText(value: string, label: string) {
  try {
    await navigator.clipboard.writeText(value);
    message.success(`Copied ${label}`);
  } catch {
    message.error("Clipboard unavailable");
  }
}

async function scanNetwork() {
  scanning.value = true;
  try {
    discovery.value = await api<MdnsDiscoveryOut>("/v1/integrations/discover?timeout=4");
    syncChoicesFromDraft();
    if (!discovery.value.available) {
      message.warning("Network scan is not available on this server.");
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
  } catch (e) {
    haTestResult.value = {
      ok: false,
      message: e instanceof ApiError ? e.message : "Home Assistant test failed",
      languages: null,
    };
  } finally {
    testingHa.value = false;
  }
}

async function testUpstream() {
  testingUpstream.value = true;
  upstreamTestResult.value = null;
  try {
    upstreamTestResult.value = await api<IntegrationConnectivityOut>(
      "/v1/integrations/wyoming/test-upstream",
      { method: "POST", json: { uri: upstreamUri.value } },
    );
  } catch (e) {
    upstreamTestResult.value = {
      ok: false,
      message: e instanceof ApiError ? e.message : "Speech-to-text test failed",
      languages: null,
    };
  } finally {
    testingUpstream.value = false;
  }
}

function applyFromServer(s: WyomingIntegrationOut) {
  const listen = parseTcp(s.uri, "0.0.0.0", 10301);
  const stt = parseTcp(s.upstream_uri, "127.0.0.1", 10300);
  server.value = s;
  draft.value = {
    enabled: s.enabled,
    listenHost: listen.host,
    listenPort: listen.port,
    sttHost: stt.host,
    sttPort: stt.port,
    home_assistant_url: s.home_assistant_url ?? "",
    require_speaker_match: s.require_speaker_match,
    block_on_gate_reject: s.block_on_gate_reject,
    tag_speaker: s.tag_speaker,
    include_confidence: Boolean(s.include_confidence),
    include_candidates: Boolean(s.include_candidates),
    zeroconf_enabled: s.zeroconf_enabled,
    zeroconf_name: s.zeroconf_name,
    advertise_host: s.advertise_host ?? "",
  };
  syncChoicesFromDraft();
}

function resetDraft() {
  if (server.value) applyFromServer(server.value);
}

async function load() {
  loading.value = true;
  try {
    applyFromServer(await api<WyomingIntegrationOut>("/v1/integrations/wyoming"));
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load Wyoming settings");
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    applyFromServer(
      await api<WyomingIntegrationOut>("/v1/integrations/wyoming", {
        method: "PATCH",
        json: {
          enabled: draft.value.enabled,
          uri: listenUri.value,
          upstream_uri: upstreamUri.value,
          home_assistant_url: draft.value.home_assistant_url.trim() || null,
          require_speaker_match: draft.value.require_speaker_match,
          block_on_gate_reject: draft.value.block_on_gate_reject,
          tag_speaker: draft.value.tag_speaker,
          include_confidence: draft.value.include_confidence,
          include_candidates: draft.value.include_candidates,
          zeroconf_enabled: draft.value.zeroconf_enabled,
          zeroconf_name: draft.value.zeroconf_name,
          advertise_host: draft.value.advertise_host.trim() || null,
        },
      }),
    );
    if (server.value?.upstream_ready) upstreamTestResult.value = null;
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
        Home Assistant Assist connects here. We hear who is speaking, then pass the audio to your
        speech-to-text service.
      </p>
      <div v-if="dirty" class="int-panel__actions">
        <NButton :disabled="saving" @click="resetDraft">Discard</NButton>
        <NButton type="primary" :loading="saving" @click="save">Save</NButton>
      </div>
    </header>

    <ContentSkeleton v-if="loading" variant="form" />

    <template v-else>
      <div class="conn-status">
        <div>
          <div class="conn-status__title">Accept connections from Home Assistant</div>
          <p class="conn-status__hint">
            Turn this on after the speech-to-text address looks right.
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
            <h3 class="conn-block__title">Add in Home Assistant</h3>
            <p class="conn-block__desc">
              Settings → Devices & services → Add integration → Wyoming Protocol.
            </p>
          </div>
        </div>
        <div class="wy-ha-card">
          <div class="wy-ha-row">
            <span class="conn-field__label">Host</span>
            <code>{{ haConnectHost }}</code>
            <NButton size="small" quaternary @click="copyText(haConnectHost, 'host')">
              <template #icon>
                <NIcon :component="CopyOutline" />
              </template>
              Copy
            </NButton>
          </div>
          <div class="wy-ha-row">
            <span class="conn-field__label">Port</span>
            <code>{{ listenPort }}</code>
            <NButton size="small" quaternary @click="copyText(String(listenPort), 'port')">
              <template #icon>
                <NIcon :component="CopyOutline" />
              </template>
              Copy
            </NButton>
          </div>
        </div>
        <p class="conn-field__hint">
          If Home Assistant does not find this server on its own, add those values by hand.
        </p>
      </section>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">Speech-to-text</h3>
            <p class="conn-block__desc">
              After a voice is recognized, the audio goes here to become words. Faster Whisper is a
              common choice.
            </p>
          </div>
          <NButton :loading="scanning" @click="scanNetwork">Scan the network</NButton>
        </div>

        <NSelect
          v-if="upstreamOptions.length > 1"
          v-model:value="upstreamChoice"
          :options="upstreamOptions"
          :loading="scanning"
          filterable
          placeholder="Choose a service, or type an address"
        />

        <div class="conn-split">
          <div class="conn-field">
            <span class="conn-field__label">Address</span>
            <NInput
              v-model:value="draft.sttHost"
              :disabled="!upstreamManual"
              placeholder="127.0.0.1"
            />
          </div>
          <div class="conn-field">
            <span class="conn-field__label">Port</span>
            <NInputNumber
              v-model:value="draft.sttPort"
              :disabled="!upstreamManual"
              :min="1"
              :max="65535"
              style="width: 100%"
            />
          </div>
        </div>
        <div class="int-panel__actions">
          <NButton :loading="testingUpstream" @click="testUpstream">Test speech-to-text</NButton>
          <NTag
            v-if="upstreamTestResult"
            round
            :bordered="false"
            :type="upstreamTestResult.ok ? 'success' : 'error'"
          >
            {{ upstreamTestResult.ok ? "Reachable" : "Not reachable" }}
          </NTag>
        </div>
        <p v-if="upstreamTestResult" class="conn-field__hint">{{ upstreamTestResult.message }}</p>
        <p
          v-if="upstreamTestResult?.ok && upstreamTestResult.languages?.length"
          class="conn-field__hint"
        >
          Languages: {{ upstreamTestResult.languages.join(", ") }}
        </p>
      </section>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">When someone speaks</h3>
            <p class="conn-block__desc">
              What happens after a voice is heard. To make it easier or harder for one person,
              set a custom inclusion level on that enrollment.
            </p>
          </div>
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
            <span class="conn-switch__label">Add the person's name</span>
            <p class="conn-switch__hint">
              Starts the message with a <code>[speaker]</code> block so Assist knows who spoke.
            </p>
          </div>
          <NSwitch v-model:value="draft.tag_speaker" />
        </div>

        <div class="conn-switch">
          <div class="conn-switch__copy">
            <span class="conn-switch__label">Add the confidence score</span>
            <p class="conn-switch__hint">
              Adds a percent next to each name, such as <code>Luke: 92%</code>.
            </p>
          </div>
          <NSwitch v-model:value="draft.include_confidence" />
        </div>

        <div class="conn-switch">
          <div class="conn-switch__copy">
            <span class="conn-switch__label">List every likely speaker</span>
            <p class="conn-switch__hint">
              Lists the other close matches under the same block, not only the top person.
            </p>
          </div>
          <NSwitch v-model:value="draft.include_candidates" />
        </div>

        <div
          v-if="draft.tag_speaker || draft.include_confidence || draft.include_candidates"
          class="conn-field"
        >
          <span class="conn-field__label">Example message</span>
          <p class="conn-field__hint">
            Speaker list first. After a blank line, <code>[transcript]</code> marks the spoken words.
          </p>
          <pre class="wh-json">{{ transcriptExample }}</pre>
        </div>
      </section>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">How this server listens</h3>
            <p class="conn-block__desc">
              Home Assistant connects to this address. Use 0.0.0.0 to accept connections from the
              whole network.
            </p>
          </div>
        </div>

        <div class="conn-split">
          <div class="conn-field">
            <span class="conn-field__label">Listen address</span>
            <NInput v-model:value="draft.listenHost" placeholder="0.0.0.0" />
          </div>
          <div class="conn-field">
            <span class="conn-field__label">Port</span>
            <NInputNumber
              v-model:value="draft.listenPort"
              :min="1"
              :max="65535"
              style="width: 100%"
            />
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
            This computer's LAN address, especially when the server runs in Docker. Leave blank to
            choose automatically.
          </p>
          <NInput
            v-model:value="draft.advertise_host"
            placeholder="192.168.1.10"
            :disabled="!draft.zeroconf_enabled"
          />
        </div>
      </section>

      <section class="conn-block">
        <div class="conn-block__head">
          <div>
            <h3 class="conn-block__title">Can this server reach Home Assistant?</h3>
            <p class="conn-block__desc">
              Optional check only. Wyoming does not need this URL to work.
            </p>
          </div>
        </div>
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
        </div>
        <p v-if="haTestResult" class="conn-field__hint">{{ haTestResult.message }}</p>
      </section>

      <StickySaveBar :dirty="dirty" :saving="saving" @save="save" @discard="resetDraft" />
    </template>
  </div>
</template>
