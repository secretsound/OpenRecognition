<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NSelect,
  NSwitch,
  NButton,
  NSpace,
  NDescriptions,
  NDescriptionsItem,
  NInputNumber,
  NSlider,
  NAlert,
  NTag,
  NPopconfirm,
  NIcon,
  useMessage,
} from "naive-ui";
import type { SelectOption } from "naive-ui";
import { PowerOutline, CopyOutline } from "@vicons/ionicons5";
import { api, loadFailureMessage } from "@/api/client";
import type { AppSettingsOut, ServiceRestartOut } from "@/types/api";
import PageHeader from "@/components/kit/PageHeader.vue";
import SegmentedControl from "@/components/kit/SegmentedControl.vue";
import StickySaveBar from "@/components/kit/StickySaveBar.vue";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import EmptyState from "@/components/EmptyState.vue";
import SettingsSection from "@/components/settings/SettingsSection.vue";
import SettingRow from "@/components/settings/SettingRow.vue";
import { ApiError } from "@/api/client";
import { featureFlagEntries } from "@/utils/featureFlags";
import { useTheme } from "@/composables/useTheme";
import { useUnsavedGuard } from "@/composables/useUnsaved";
import { webUiVersion, buildRuntime } from "@/buildInfo";
import { ensureSystemInfo, lanApiUrls as buildLanUrls } from "@/utils/settingsSystem";

const message = useMessage();
const router = useRouter();
const { mode, setTheme, accentId, setAccent, accentOptions, themeModeOptions } = useTheme();

type SettingsTab = "appearance" | "recognition" | "security" | "system" | "advanced";
const settingsTabs: { value: SettingsTab; label: string }[] = [
  { value: "appearance", label: "Appearance" },
  { value: "recognition", label: "Recognition" },
  { value: "security", label: "Security" },
  { value: "system", label: "System" },
  { value: "advanced", label: "Advanced" },
];

const loading = ref(true);
const loadError = ref<string | null>(null);
const saving = ref(false);
const restarting = ref(false);
const settings = ref<AppSettingsOut | null>(null);
const activeTab = ref<SettingsTab>("appearance");

const draft = ref({
  maintenance_mode: false,
  enrollment_media_retention: "embeddings_only" as string,
  feature_flags: {} as Record<string, boolean>,
  default_min_confidence: 0.75,
  default_return_unknown: true,
  default_include_sound_events: false,
  recognition_log_retention_days: 0,
  session_ttl_minutes: 60,
  model_idle_unload_minutes: 0,
});

const retentionOptions: SelectOption[] = [
  { label: "Embeddings only (recommended)", value: "embeddings_only" },
  { label: "Keep original media files", value: "keep" },
];

const logRetentionOptions: SelectOption[] = [
  { label: "Keep forever", value: 0 },
  { label: "7 days", value: 7 },
  { label: "30 days", value: 30 },
  { label: "90 days", value: 90 },
  { label: "365 days", value: 365 },
];

const flagRows = computed(() => featureFlagEntries(draft.value.feature_flags));

const system = computed(() => settings.value?.system ?? null);

const browserOrigin = computed(() =>
  typeof window !== "undefined" ? window.location.origin : "",
);

const lanUrls = computed(() => (settings.value ? buildLanUrls(settings.value) : []));

const systemStale = computed(() => system.value?.python_version === "—");

const inferenceBackendLabel = computed(() => {
  const b = settings.value?.inference_backend ?? "auto";
  if (b === "auto") return "Auto (ONNX when available)";
  if (b === "onnx") return "ONNX";
  return "Heuristic";
});

const loadedModelCount = computed(() => {
  const models = settings.value?.inference_status?.models;
  return models ? Object.keys(models).length : null;
});

const confidencePercent = computed({
  get: () => Math.round(draft.value.default_min_confidence * 100),
  set: (v: number) => {
    draft.value.default_min_confidence = v / 100;
  },
});

function numField<K extends keyof typeof draft.value>(key: K, server: AppSettingsOut): boolean {
  return (draft.value[key] as number) !== (server[key] as number);
}

const dirty = computed(() => {
  if (!settings.value) return false;
  const s = settings.value;
  if (draft.value.maintenance_mode !== s.maintenance_mode) return true;
  if (draft.value.enrollment_media_retention !== s.enrollment_media_retention) return true;
  if (draft.value.default_min_confidence !== s.default_min_confidence) return true;
  if (draft.value.default_return_unknown !== s.default_return_unknown) return true;
  if (draft.value.default_include_sound_events !== s.default_include_sound_events) return true;
  if (draft.value.recognition_log_retention_days !== s.recognition_log_retention_days) return true;
  if (draft.value.session_ttl_minutes !== s.session_ttl_minutes) return true;
  if (numField("model_idle_unload_minutes", s)) return true;
  for (const row of flagRows.value) {
    if ((s.feature_flags[row.key] ?? false) !== (draft.value.feature_flags[row.key] ?? false)) {
      return true;
    }
  }
  return false;
});

function applyFromServer(s: AppSettingsOut) {
  settings.value = s;
  draft.value = {
    maintenance_mode: s.maintenance_mode,
    enrollment_media_retention: s.enrollment_media_retention,
    feature_flags: { ...s.feature_flags },
    default_min_confidence: s.default_min_confidence,
    default_return_unknown: s.default_return_unknown,
    default_include_sound_events: s.default_include_sound_events,
    recognition_log_retention_days: s.recognition_log_retention_days,
    session_ttl_minutes: s.session_ttl_minutes,
    model_idle_unload_minutes: s.model_idle_unload_minutes,
  };
}

async function fetchHealth(): Promise<{ version?: string } | null> {
  try {
    const res = await fetch("/health", { credentials: "include" });
    if (!res.ok) return null;
    return (await res.json()) as { version?: string };
  } catch {
    return null;
  }
}

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    const [raw, health] = await Promise.all([
      api<AppSettingsOut>("/v1/admin/settings"),
      fetchHealth(),
    ]);
    applyFromServer(ensureSystemInfo(raw, health));
  } catch (e) {
    loadError.value = loadFailureMessage(e, "Failed to load settings");
    message.error(loadError.value);
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const raw = await api<AppSettingsOut>("/v1/admin/settings", {
      method: "PATCH",
      json: {
        maintenance_mode: draft.value.maintenance_mode,
        enrollment_media_retention: draft.value.enrollment_media_retention,
        feature_flags: { ...draft.value.feature_flags },
        default_min_confidence: draft.value.default_min_confidence,
        default_return_unknown: draft.value.default_return_unknown,
        default_include_sound_events: draft.value.default_include_sound_events,
        recognition_log_retention_days: draft.value.recognition_log_retention_days,
        session_ttl_minutes: draft.value.session_ttl_minutes,
        model_idle_unload_minutes: draft.value.model_idle_unload_minutes,
      },
    });
    const health = await fetchHealth();
    applyFromServer(ensureSystemInfo(raw, health));
    message.success("Settings saved");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to save settings");
  } finally {
    saving.value = false;
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

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForServiceBack(timeoutMs = 90_000) {
  await sleep(1200);
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch("/health", { credentials: "include" });
      if (res.ok) return;
    } catch {
      /* service down */
    }
    await sleep(1500);
  }
  throw new Error("Timed out waiting for the service to come back");
}

async function restartService() {
  restarting.value = true;
  try {
    if (dirty.value) await save();
    const res = await api<ServiceRestartOut>("/v1/admin/restart", { method: "POST" });
    message.info(res.message);
    await waitForServiceBack();
    message.success("Service restarted");
    await load();
  } catch (e) {
    message.error(e instanceof Error ? e.message : "Restart failed");
  } finally {
    restarting.value = false;
  }
}

function setFlag(key: string, value: boolean) {
  draft.value.feature_flags = { ...draft.value.feature_flags, [key]: value };
}

function resetDraft() {
  if (settings.value) applyFromServer(settings.value);
}

useUnsavedGuard(dirty);

onMounted(load);
</script>

<template>
  <div class="or-page or-page--prose">
    <PageHeader
      title="Settings"
      description="Appearance, recognition defaults, who can sign in, and how this server is running."
    >
      <template #tabs>
        <SegmentedControl
          v-model="activeTab"
          aria-label="Settings sections"
          :options="settingsTabs"
        />
      </template>
    </PageHeader>

    <ContentSkeleton v-if="loading && !settings" variant="detail" />
    <EmptyState
      v-else-if="loadError && !settings"
      title="Couldn't load settings"
      :description="loadError"
      action-label="Retry"
      @action="load"
    />

    <template v-else-if="settings && system">
      <section v-if="activeTab === 'appearance'" class="tab-panel">
              <SettingsSection title="Theme">
                <SettingRow label="Color mode">
                  <SegmentedControl
                    :model-value="mode"
                    :options="themeModeOptions"
                    aria-label="Color mode"
                    @update:model-value="setTheme"
                  />
                  <template #hint>Stored in this browser. System follows the OS.</template>
                </SettingRow>
                <SettingRow label="Accent">
                  <div class="accent-swatches">
                    <button
                      v-for="opt in accentOptions"
                      :key="opt.value"
                      type="button"
                      class="swatch"
                      :class="{ 'is-active': accentId === opt.value }"
                      :style="{ background: opt.color }"
                      :aria-label="opt.label"
                      :title="opt.label"
                      @click="setAccent(opt.value)"
                    />
                  </div>
                  <template #hint>
                    Buttons, links, navigation, and the sidebar logo.
                  </template>
                </SettingRow>
              </SettingsSection>
      </section>

      <section v-if="activeTab === 'recognition'" class="tab-panel">
              <SettingsSection
                title="Defaults"
                description="Used when a request does not set its own options."
              >
                <SettingRow :label="`Match threshold (${confidencePercent}%)`">
                  <div class="slider-wrap">
                    <NSlider
                      v-model:value="confidencePercent"
                      :min="50"
                      :max="95"
                      :step="1"
                    />
                  </div>
                </SettingRow>
                <SettingRow label="Return unknown identities">
                  <NSwitch v-model:value="draft.default_return_unknown" />
                  <template #hint>
                    Report low-confidence matches as <code>unknown</code> instead of omitting them.
                  </template>
                </SettingRow>
                <SettingRow label="Sound events by default">
                  <NSwitch v-model:value="draft.default_include_sound_events" />
                  <template #hint>
                    Heuristic labels on audio requests (glass break, bark, etc.).
                  </template>
                </SettingRow>
              </SettingsSection>

              <SettingsSection title="Models">
                <SettingRow label="Inference">
                  <NButton @click="router.push('/models')">Open Models</NButton>
                  <template #hint>
                    Currently {{ inferenceBackendLabel }}. Download or reload weights on the Models page.
                  </template>
                </SettingRow>
              </SettingsSection>

              <SettingsSection title="Samples">
                <SettingRow label="Keep original files">
                  <NSelect
                    v-model:value="draft.enrollment_media_retention"
                    :options="retentionOptions"
                    style="width: 280px"
                  />
                  <template #hint>
                    Embeddings are the compact fingerprints used for matching. You can keep the original files or only those fingerprints.
                  </template>
                </SettingRow>
                <SettingRow label="Activity retention">
                  <NSelect
                    v-model:value="draft.recognition_log_retention_days"
                    :options="logRetentionOptions"
                    style="width: 200px"
                  />
                  <template #hint>How long Activity keeps events. View them on the Activity page.</template>
                </SettingRow>
              </SettingsSection>
      </section>

      <section v-if="activeTab === 'security'" class="tab-panel">
              <SettingsSection title="Sessions & limits">
                <SettingRow label="Web session lifetime">
                  <NSpace align="center" :size="8">
                    <NInputNumber
                      v-model:value="draft.session_ttl_minutes"
                      :min="5"
                      :max="10080"
                      style="width: 120px"
                    />
                    <span class="unit">min</span>
                  </NSpace>
                  <template #hint>
                    Browser login duration. Active sessions keep their original expiry.
                  </template>
                </SettingRow>
                <SettingRow label="Maintenance mode">
                  <NSwitch v-model:value="draft.maintenance_mode" />
                  <template #hint>
                    Pauses recognition and new samples. You can still use this console.
                  </template>
                </SettingRow>
                <SettingRow label="API rate limit">
                  <NTag size="small" round :bordered="false">
                    {{ settings.auth_rate_limit_per_minute }} / min
                  </NTag>
                  <template #hint>
                    Set via <code>OPENRECOGNITION_AUTH_RATE_LIMIT_PER_MINUTE</code> (enforcement pending).
                  </template>
                </SettingRow>
              </SettingsSection>
      </section>

      <section v-if="activeTab === 'system'" class="tab-panel">
              <NAlert type="info" :bordered="false" class="system-warn">
                Saved changes are stored in
                <code>{{ settings.runtime_settings_path || "data/runtime_settings.json" }}</code>.
                Pack, bind address, and auth come from environment variables.
              </NAlert>
              <SettingsSection title="Process">
                <SettingRow label="Unload idle models">
                  <NSpace align="center" :size="8">
                    <NInputNumber
                      v-model:value="draft.model_idle_unload_minutes"
                      :min="0"
                      :max="1440"
                      style="width: 120px"
                    />
                    <span class="unit">min (0 = never)</span>
                  </NSpace>
                  <template #hint>
                    Free memory by unloading models that have not been used. ONNX is the optional faster engine.
                  </template>
                </SettingRow>
                <SettingRow label="Restart service">
                  <NPopconfirm
                    positive-text="Restart"
                    negative-text="Cancel"
                    @positive-click="restartService"
                  >
                    <template #trigger>
                      <NButton secondary :loading="restarting">
                        <template #icon>
                          <NIcon><PowerOutline /></NIcon>
                        </template>
                        Restart now
                      </NButton>
                    </template>
                    Restart the API? Unsaved changes are saved first.
                  </NPopconfirm>
                  <template #hint>
                    The server pauses briefly. Docker or systemd environment changes need a container recreate.
                  </template>
                </SettingRow>
              </SettingsSection>
              <NAlert
                v-if="systemStale"
                type="warning"
                :bordered="false"
                class="system-warn"
                title="Limited system info"
              >
                Restart the OpenRecognition API to load full host and Python details.
              </NAlert>

              <div class="system-grid">
                <SettingsSection title="Versions">
                  <NDescriptions :column="1" label-placement="left" size="small">
                    <NDescriptionsItem label="OpenRecognition">
                      <NTag size="small" round :bordered="false">{{ system.server_version }}</NTag>
                    </NDescriptionsItem>
                    <NDescriptionsItem label="Python">
                      {{ system.python_version }}
                    </NDescriptionsItem>
                    <NDescriptionsItem label="Web UI">
                      {{ webUiVersion }}
                    </NDescriptionsItem>
                    <NDescriptionsItem label="Built with">
                      {{ buildRuntime }}
                    </NDescriptionsItem>
                    <NDescriptionsItem label="Platform">
                      <span class="mono">{{ system.platform }}</span>
                    </NDescriptionsItem>
                  </NDescriptions>
                </SettingsSection>

                <SettingsSection title="Network">
                  <NDescriptions :column="1" label-placement="left" size="small">
                    <NDescriptionsItem label="Hostname">
                      {{ system.hostname }}
                    </NDescriptionsItem>
                    <NDescriptionsItem label="API bind">
                      {{ system.api_bind }}
                    </NDescriptionsItem>
                    <NDescriptionsItem label="Local API">
                      <span class="copy-line">
                        <code class="mono">{{ system.api_local_url }}</code>
                        <NButton
                          quaternary
                          size="tiny"
                          aria-label="Copy local API URL"
                          @click="copyText(system.api_local_url, 'URL')"
                        >
                          <template #icon>
                            <NIcon :component="CopyOutline" />
                          </template>
                        </NButton>
                      </span>
                    </NDescriptionsItem>
                    <NDescriptionsItem label="LAN">
                      <template v-if="lanUrls.length">
                        <div class="url-list">
                          <span
                            v-for="url in lanUrls"
                            :key="url"
                            class="copy-line"
                          >
                            <code class="mono">{{ url }}</code>
                            <NButton
                              quaternary
                              size="tiny"
                              :aria-label="`Copy ${url}`"
                              @click="copyText(url, 'URL')"
                            >
                              <template #icon>
                                <NIcon :component="CopyOutline" />
                              </template>
                            </NButton>
                          </span>
                        </div>
                      </template>
                      <span v-else class="muted">None detected</span>
                    </NDescriptionsItem>
                    <NDescriptionsItem label="This browser">
                      <code class="mono">{{ browserOrigin || "—" }}</code>
                    </NDescriptionsItem>
                    <NDescriptionsItem v-if="system.web_origin" label="CORS origin">
                      <code class="mono">{{ system.web_origin }}</code>
                    </NDescriptionsItem>
                  </NDescriptions>
                </SettingsSection>

                <SettingsSection title="Deployment">
                  <NDescriptions :column="1" label-placement="left" size="small">
                    <NDescriptionsItem label="Hardware">
                      <NTag size="small" round :bordered="false" type="info">{{ settings.hardware.label }}</NTag>
                    </NDescriptionsItem>
                    <NDescriptionsItem label="Auth">
                      {{ settings.auth_required ? "Required" : "Off" }}
                    </NDescriptionsItem>
                    <NDescriptionsItem label="Data">
                      <span class="mono">{{ settings.data_dir }}</span>
                    </NDescriptionsItem>
                    <NDescriptionsItem label="Models">
                      <span class="mono">{{ settings.models_dir }}</span>
                    </NDescriptionsItem>
                    <NDescriptionsItem label="Web UI">
                      {{ settings.web_enabled ? "Enabled" : "Disabled" }}
                    </NDescriptionsItem>
                    <NDescriptionsItem label="API docs">
                      {{ settings.docs_enabled ? "Enabled" : "Disabled" }}
                    </NDescriptionsItem>
                    <NDescriptionsItem label="Inference">
                      {{ inferenceBackendLabel }}
                      <NButton
                        text
                        type="primary"
                        size="tiny"
                        class="inline-link"
                        @click="router.push('/models')"
                      >
                        Models →
                      </NButton>
                    </NDescriptionsItem>
                    <NDescriptionsItem label="Loaded models">
                      {{ loadedModelCount ?? "—" }}
                    </NDescriptionsItem>
                  </NDescriptions>
                </SettingsSection>

                <SettingsSection
                  title="Environment"
                  description="Requires service restart (Docker, systemd, or manual)."
                >
                  <NSpace size="small">
                    <NTag
                      v-for="key in settings.restart_required_for"
                      :key="key"
                      size="small"
                      round
                      :bordered="false"
                    >
                      OPENRECOGNITION_{{ key.toUpperCase() }}
                    </NTag>
                  </NSpace>
                  <p class="env-examples">
                    <code>OPENRECOGNITION_MODELS_DIR=./models</code>
                    <code>OPENRECOGNITION_HOST=0.0.0.0</code>
                    <code>OPENRECOGNITION_PORT=8080</code>
                  </p>
                </SettingsSection>
              </div>
      </section>

      <section v-if="activeTab === 'advanced'" class="tab-panel">
              <SettingsSection
                title="Recognition paths"
                description="Turn individual ways of recognizing on or off."
              >
                <SettingRow
                  v-for="row in flagRows"
                  :key="row.key"
                  :label="row.label"
                >
                  <NSwitch
                    :value="draft.feature_flags[row.key] ?? false"
                    @update:value="(v: boolean) => setFlag(row.key, v)"
                  />
                  <template v-if="row.description" #hint>{{ row.description }}</template>
                </SettingRow>
              </SettingsSection>
      </section>
      <StickySaveBar :dirty="dirty" :saving="saving" @save="save" @discard="resetDraft" />
    </template>
  </div>
</template>

<style scoped>
.tab-panel {
  max-width: 640px;
}

.system-grid {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-width: 100%;
}

.system-grid .settings-section {
  max-width: 560px;
}

.system-warn {
  margin-bottom: 12px;
  max-width: 560px;
}

.models-link {
  margin: 0 0 12px;
  font-size: 0.8125rem;
  color: var(--n-text-color-3);
}

.slider-wrap {
  width: 220px;
}

.accent-swatches {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.swatch {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  border: 2px solid transparent;
  cursor: pointer;
  padding: 0;
}

.swatch.is-active {
  box-shadow: 0 0 0 2px var(--or-surface), 0 0 0 4px var(--or-accent);
}

.pipeline-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--n-border-color);
}

.pipeline-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.pipeline-row__label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
}

.pipeline-row__desc {
  display: block;
  margin-top: 4px;
  font-size: 0.8rem;
  color: var(--n-text-color-3);
  line-height: 1.4;
}

.unit {
  font-size: 0.8125rem;
  color: var(--n-text-color-3);
}

.mono {
  font-size: 0.75rem;
  word-break: break-all;
}

.muted {
  color: var(--n-text-color-3);
  font-size: 0.8125rem;
}

.copy-line {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
}

.url-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.env-examples {
  margin: 12px 0 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.env-examples code {
  font-size: 0.7rem;
  padding: 4px 8px;
  border-radius: 6px;
  background: var(--n-action-color);
}

.inline-link {
  margin-left: 6px;
}

@media (max-width: 768px) {
  .tab-panel {
    padding-inline: 0;
  }
}
</style>
