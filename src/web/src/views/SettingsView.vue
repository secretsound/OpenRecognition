<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  NAlert,
  NButton,
  NIcon,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSelect,
  NSlider,
  NSpace,
  NSwitch,
  useMessage,
} from "naive-ui";
import type { SelectOption } from "naive-ui";
import { CopyOutline, PowerOutline } from "@vicons/ionicons5";
import { api, ApiError, loadFailureMessage } from "@/api/client";
import type { AppSettingsOut, ServiceRestartOut } from "@/types/api";
import PageHeader from "@/components/kit/PageHeader.vue";
import SegmentedControl from "@/components/kit/SegmentedControl.vue";
import StickySaveBar from "@/components/kit/StickySaveBar.vue";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import EmptyState from "@/components/EmptyState.vue";
import SettingsSection from "@/components/settings/SettingsSection.vue";
import SettingRow from "@/components/settings/SettingRow.vue";
import NetworkSettings from "@/components/settings/NetworkSettings.vue";
import StorageSettings from "@/components/settings/StorageSettings.vue";
import BackupSettings from "@/components/settings/BackupSettings.vue";
import LogsSettings from "@/components/settings/LogsSettings.vue";
import SsoSettings from "@/components/settings/SsoSettings.vue";
import {
  draftDirty,
  draftError,
  draftFrom,
  draftPatch,
  type SettingsDraft,
} from "@/components/settings/settingsDraft";
import { featureFlagEntries } from "@/utils/featureFlags";
import { useTheme } from "@/composables/useTheme";
import { useUnsavedGuard } from "@/composables/useUnsaved";
import { webUiVersion, buildRuntime } from "@/buildInfo";
import { ensureSystemInfo, lanApiUrls as buildLanUrls } from "@/utils/settingsSystem";
import { setLocale, t } from "@/i18n";
import { setDisplayTimeZone } from "@/utils/time";

const message = useMessage();
const router = useRouter();
const { mode, setTheme, accentId, setAccent, accentOptions, themeModeOptions } = useTheme();

type Section =
  | "general"
  | "network"
  | "storage"
  | "backup"
  | "logs"
  | "security"
  | "sso"
  | "recognition"
  | "advanced"
  | "system";

const sections: { id: Section; key: string }[] = [
  { id: "general", key: "settings.section.general" },
  { id: "network", key: "settings.section.network" },
  { id: "storage", key: "settings.section.storage" },
  { id: "backup", key: "settings.section.backup" },
  { id: "logs", key: "settings.section.logs" },
  { id: "security", key: "settings.section.security" },
  { id: "sso", key: "sso.title" },
  { id: "recognition", key: "settings.section.recognition" },
  { id: "advanced", key: "settings.section.advanced" },
  { id: "system", key: "settings.section.system" },
];

const loading = ref(true);
const loadError = ref<string | null>(null);
const saving = ref(false);
const restarting = ref(false);
const settings = ref<AppSettingsOut | null>(null);
const section = ref<Section>("general");
const draft = ref<SettingsDraft | null>(null);

const languages = [
  { value: "en", label: "English" },
  { value: "es", label: "Español" },
  { value: "fr", label: "Français" },
  { value: "de", label: "Deutsch" },
  { value: "pt", label: "Português" },
  { value: "zh", label: "中文" },
];

const themeOptions = computed(() =>
  themeModeOptions.map((opt) => ({ ...opt, label: t(`theme.${opt.value}`) })),
);

const retentionOptions = computed<SelectOption[]>(() => [
  { label: t("recognition.keepEmbeddings"), value: "embeddings_only" },
  { label: t("recognition.keepFiles"), value: "keep" },
]);

const logRetentionOptions = computed<SelectOption[]>(() => [
  { label: t("recognition.forever"), value: 0 },
  { label: t("recognition.days", { n: 7 }), value: 7 },
  { label: t("recognition.days", { n: 30 }), value: 30 },
  { label: t("recognition.days", { n: 90 }), value: 90 },
  { label: t("recognition.days", { n: 365 }), value: 365 },
]);

const flagCopy: Record<string, { label: string; description: string }> = {
  "biometrics.face_enabled": { label: "flag.face", description: "flag.faceDesc" },
  "biometrics.speaker_enabled": { label: "flag.speaker", description: "flag.speakerDesc" },
  "biometrics.pet_enabled": { label: "flag.pet", description: "flag.petDesc" },
  "recognition.sound_events_enabled": { label: "flag.sounds", description: "flag.soundsDesc" },
};

const flagRows = computed(() =>
  featureFlagEntries(draft.value?.feature_flags ?? {}).map((row) => ({
    ...row,
    label: flagCopy[row.key] ? t(flagCopy[row.key].label) : row.label,
    description: flagCopy[row.key] ? t(flagCopy[row.key].description) : row.description,
  })),
);

const system = computed(() => settings.value?.system ?? null);
const browserOrigin = computed(() => (typeof window !== "undefined" ? window.location.origin : ""));
const lanUrls = computed(() => (settings.value ? buildLanUrls(settings.value) : []));
const showAllLan = ref(false);
const visibleLan = computed(() => (showAllLan.value ? lanUrls.value : lanUrls.value.slice(0, 2)));
const hiddenLan = computed(() => Math.max(0, lanUrls.value.length - 2));
const systemStale = computed(() => system.value?.python_version === "—");

const osSummary = computed(() => {
  const raw = system.value?.platform ?? "";
  if (!raw || raw === "—") return { name: "—", detail: "" };
  const [os, kernel = ""] = raw.split("-");
  const name =
    os === "Darwin" ? "macOS" : os === "Linux" ? "Linux" : os.startsWith("Windows") ? "Windows" : os;
  const arch = raw.match(/\b(x86_64|aarch64|arm64|amd64|i386|armv7l)\b/)?.[1] ?? "";
  return { name, detail: [arch, kernel].filter(Boolean).join(" · ") };
});

const inferenceBackendLabel = computed(() => {
  const backend = settings.value?.inference_backend ?? "auto";
  if (backend === "auto") return t("recognition.auto");
  if (backend === "onnx") return t("recognition.onnx");
  return t("recognition.heuristic");
});

const loadedModelCount = computed(() => {
  const models = settings.value?.inference_status?.models;
  return models ? Object.keys(models).length : null;
});

const confidencePercent = computed({
  get: () => Math.round((draft.value?.default_min_confidence ?? 0.75) * 100),
  set: (value: number) => {
    if (draft.value) draft.value.default_min_confidence = value / 100;
  },
});

const dirty = computed(() =>
  settings.value && draft.value ? draftDirty(draft.value, settings.value) : false,
);

const errorKey = computed(() =>
  draft.value ? draftError(draft.value, Boolean(settings.value?.oidc_client_secret_set)) : null,
);

const restartPending = computed(() => settings.value?.restart_pending ?? []);

const timeZones = computed(() => {
  const intl = Intl as typeof Intl & { supportedValuesOf?: (key: string) => string[] };
  const zones = intl.supportedValuesOf?.("timeZone") ?? [];
  return ["UTC", ...zones.filter((zone) => zone !== "UTC")].map((value) => ({ label: value, value }));
});

const monitorBase = computed(() => {
  const pub = (draft.value?.public_url || settings.value?.public_url || "").trim().replace(/\/$/, "");
  if (pub) return pub;
  const local = system.value?.api_local_url || "";
  try {
    return new URL(local).origin;
  } catch {
    return local.replace(/\/$/, "");
  }
});

watch(
  () => draft.value?.display_language,
  (code) => {
    if (code) setLocale(code);
  },
);

watch(
  () => draft.value?.display_timezone,
  (zone) => {
    if (zone) setDisplayTimeZone(zone);
  },
);

function applyFromServer(value: AppSettingsOut) {
  settings.value = value;
  draft.value = draftFrom(value);
  setLocale(value.display_language ?? "en");
  setDisplayTimeZone(value.display_timezone || "UTC");
}

function generateMetricsToken() {
  if (!draft.value) return;
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  draft.value.metrics_token = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  draft.value.clear_metrics_token = false;
}

function clearMetricsToken() {
  if (!draft.value) return;
  draft.value.metrics_token = "";
  draft.value.clear_metrics_token = true;
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
    loadError.value = loadFailureMessage(e, t("settings.loadFailed"));
    message.error(loadError.value);
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (!draft.value) return;
  if (errorKey.value) {
    message.error(t(errorKey.value));
    return;
  }
  if (draft.value.port == null || draft.value.https_port == null || draft.value.session_ttl_minutes == null) {
    return;
  }
  saving.value = true;
  try {
    const raw = await api<AppSettingsOut>("/v1/admin/settings", {
      method: "PATCH",
      json: draftPatch(draft.value),
    });
    const health = await fetchHealth();
    applyFromServer(ensureSystemInfo(raw, health));
    message.success(t("settings.saved"));
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : t("settings.saveFailed"));
  } finally {
    saving.value = false;
  }
}

async function copyText(text: string, label: string) {
  try {
    await navigator.clipboard.writeText(text);
    message.success(t("settings.copied", { label }));
  } catch {
    message.error(t("settings.copyFailed"));
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
  throw new Error(t("settings.restartWait"));
}

async function restartService() {
  restarting.value = true;
  try {
    if (dirty.value) await save();
    const res = await api<ServiceRestartOut>("/v1/admin/restart", { method: "POST" });
    message.info(res.message);
    await waitForServiceBack();
    message.success(t("settings.restarted"));
    await load();
  } catch (e) {
    message.error(e instanceof Error ? e.message : t("settings.restartFailed"));
  } finally {
    restarting.value = false;
  }
}

function setFlag(key: string, value: boolean) {
  if (!draft.value) return;
  draft.value.feature_flags = { ...draft.value.feature_flags, [key]: value };
}

function resetDraft() {
  if (settings.value) applyFromServer(settings.value);
}

useUnsavedGuard(dirty);

onMounted(load);
onUnmounted(() => {
  const saved = settings.value?.display_language;
  if (saved && draft.value && draft.value.display_language !== saved) setLocale(saved);
  if (settings.value) setDisplayTimeZone(settings.value.display_timezone || "UTC");
});
</script>

<template>
  <div class="or-page settings-page">
    <PageHeader :title="t('settings.title')" :description="t('settings.lead')" />

    <ContentSkeleton v-if="loading && !settings" variant="detail" />
    <EmptyState
      v-else-if="loadError && !settings"
      :title="t('settings.loadTitle')"
      :description="loadError"
      :action-label="t('settings.retry')"
      @action="load"
    />

    <template v-else-if="settings && system && draft">
      <NAlert v-if="restartPending.length" type="warning" :bordered="false">
        {{ t("settings.restartBanner", { keys: restartPending.join(", ") }) }}
      </NAlert>
      <NAlert v-if="errorKey" type="error" :bordered="false">{{ t(errorKey) }}</NAlert>

      <div class="settings-shell">
        <nav class="settings-nav" :aria-label="t('settings.title')">
          <button
            v-for="item in sections"
            :key="item.id"
            type="button"
            class="settings-nav__item"
            :class="{ 'is-active': section === item.id }"
            :aria-current="section === item.id ? 'page' : undefined"
            @click="section = item.id"
          >
            {{ t(item.key) }}
          </button>
        </nav>

        <div class="settings-main">
          <section v-if="section === 'general'">
            <SettingsSection :title="t('general.theme')">
              <SettingRow :label="t('general.language')">
                <NSelect v-model:value="draft.display_language" :options="languages" style="width: 200px" />
                <template #hint>{{ t("general.languageHint") }}</template>
              </SettingRow>
              <SettingRow :label="t('general.timezone')">
                <NSelect
                  v-model:value="draft.display_timezone"
                  :options="timeZones"
                  filterable
                  style="width: 280px"
                />
                <template #hint>{{ t("general.timezoneHint") }}</template>
              </SettingRow>
              <SettingRow :label="t('general.mode')">
                <SegmentedControl
                  :model-value="mode"
                  :options="themeOptions"
                  :aria-label="t('general.mode')"
                  @update:model-value="setTheme"
                />
                <template #hint>{{ t("general.modeHint") }}</template>
              </SettingRow>
              <SettingRow :label="t('general.accent')">
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
                <template #hint>{{ t("general.accentHint") }}</template>
              </SettingRow>
            </SettingsSection>
          </section>

          <NetworkSettings v-else-if="section === 'network'" :draft="draft" :settings="settings" />
          <StorageSettings v-else-if="section === 'storage'" :draft="draft" :settings="settings" />
          <BackupSettings v-else-if="section === 'backup'" />
          <LogsSettings
            v-else-if="section === 'logs'"
            :draft="draft"
            :log-file="settings.log_file ?? ''"
          />

          <section v-else-if="section === 'security'">
            <SettingsSection :title="t('security.sessions')">
              <SettingRow :label="t('security.session')">
                <NSpace align="center" :size="8">
                  <NInputNumber
                    v-model:value="draft.session_ttl_minutes"
                    :min="5"
                    :max="10080"
                    style="width: 120px"
                  />
                  <span class="unit">{{ t("security.min") }}</span>
                </NSpace>
                <template #hint>{{ t("security.sessionHint") }}</template>
              </SettingRow>
              <SettingRow :label="t('security.maintenance')">
                <NSwitch v-model:value="draft.maintenance_mode" />
                <template #hint>{{ t("security.maintenanceHint") }}</template>
              </SettingRow>
              <SettingRow :label="t('security.rate')">
                <NSpace align="center" :size="8">
                  <NInputNumber
                    v-model:value="draft.auth_rate_limit_per_minute"
                    :min="1"
                    :max="10000"
                    style="width: 120px"
                  />
                  <span class="unit">/ {{ t("security.min") }}</span>
                </NSpace>
                <template #hint>{{ t("security.rateHint") }}</template>
              </SettingRow>
            </SettingsSection>
          </section>

          <SsoSettings v-else-if="section === 'sso'" :draft="draft" :settings="settings" />

          <section v-else-if="section === 'recognition'">
            <SettingsSection :title="t('recognition.defaults')" :description="t('recognition.defaultsHint')">
              <SettingRow :label="t('recognition.threshold', { n: confidencePercent })">
                <div class="slider-wrap">
                  <NSlider v-model:value="confidencePercent" :min="50" :max="95" :step="1" />
                </div>
              </SettingRow>
              <SettingRow :label="t('recognition.unknown')">
                <NSwitch v-model:value="draft.default_return_unknown" />
                <template #hint>{{ t("recognition.unknownHint") }}</template>
              </SettingRow>
              <SettingRow :label="t('recognition.sounds')">
                <NSwitch v-model:value="draft.default_include_sound_events" />
                <template #hint>{{ t("recognition.soundsHint") }}</template>
              </SettingRow>
            </SettingsSection>
            <SettingsSection :title="t('recognition.models')">
              <SettingRow :label="t('recognition.models')">
                <NButton @click="router.push('/models')">{{ t("recognition.openModels") }}</NButton>
                <template #hint>
                  {{ t("recognition.inference", { backend: inferenceBackendLabel }) }}
                </template>
              </SettingRow>
            </SettingsSection>
            <SettingsSection :title="t('recognition.samples')">
              <SettingRow :label="t('recognition.keep')">
                <NSelect
                  v-model:value="draft.enrollment_media_retention"
                  :options="retentionOptions"
                  style="width: 280px"
                />
                <template #hint>{{ t("recognition.keepHint") }}</template>
              </SettingRow>
              <SettingRow :label="t('recognition.activity')">
                <NSelect
                  v-model:value="draft.recognition_log_retention_days"
                  :options="logRetentionOptions"
                  style="width: 200px"
                />
                <template #hint>{{ t("recognition.activityHint") }}</template>
              </SettingRow>
            </SettingsSection>
          </section>

          <section v-else-if="section === 'advanced'">
            <SettingsSection :title="t('settings.section.advanced')" :description="t('advanced.lead')">
              <SettingRow v-for="row in flagRows" :key="row.key" :label="row.label">
                <NSwitch
                  :value="draft.feature_flags[row.key] ?? false"
                  @update:value="(v: boolean) => setFlag(row.key, v)"
                />
                <template v-if="row.description" #hint>{{ row.description }}</template>
              </SettingRow>
            </SettingsSection>
          </section>

          <section v-else class="system-panel">
            <div class="glance">
              <div class="glance__item">
                <span class="or-caps">{{ t("system.product") }}</span>
                <strong>{{ system.server_version }}</strong>
              </div>
              <div class="glance__item">
                <span class="or-caps">{{ t("system.hardware") }}</span>
                <strong>{{ settings.hardware.label }}</strong>
              </div>
              <div class="glance__item">
                <span class="or-caps">{{ t("system.hostname") }}</span>
                <strong>{{ system.hostname }}</strong>
              </div>
              <div class="glance__item">
                <span class="or-caps">{{ t("system.loaded") }}</span>
                <strong>{{ loadedModelCount ?? "—" }}</strong>
              </div>
            </div>

            <SettingsSection :title="t('system.process')">
              <SettingRow :label="t('system.unload')">
                <NSpace align="center" :size="8">
                  <NInputNumber
                    v-model:value="draft.model_idle_unload_minutes"
                    :min="0"
                    :max="1440"
                    style="width: 120px"
                  />
                  <span class="unit">{{ t("system.never") }}</span>
                </NSpace>
                <template #hint>{{ t("system.unloadHint") }}</template>
              </SettingRow>
              <SettingRow :label="t('settings.restartNow')">
                <NPopconfirm
                  :positive-text="t('settings.restart')"
                  :negative-text="t('settings.cancel')"
                  @positive-click="restartService"
                >
                  <template #trigger>
                    <NButton secondary :loading="restarting">
                      <template #icon>
                        <NIcon><PowerOutline /></NIcon>
                      </template>
                      {{ t("settings.restartNow") }}
                    </NButton>
                  </template>
                  {{ t("settings.restartConfirm") }}
                </NPopconfirm>
                <template #hint>{{ t("settings.restartHint") }}</template>
              </SettingRow>
            </SettingsSection>

            <NAlert
              v-if="systemStale"
              type="warning"
              :bordered="false"
              class="system-warn"
              :title="t('system.limited')"
            >
              {{ t("system.limitedBody") }}
            </NAlert>

            <SettingsSection :title="t('system.reachTitle')" :description="t('system.reachHint')">
              <ul class="fact-list">
                <li>
                  <span class="fact-list__label">{{ t("system.onMachine") }}</span>
                  <div class="fact-list__main">
                    <span class="fact-list__value or-mono">{{ system.api_local_url }}</span>
                    <NButton
                      quaternary
                      circle
                      size="small"
                      :aria-label="t('system.copy')"
                      @click="copyText(system.api_local_url, t('system.local'))"
                    >
                      <template #icon><NIcon><CopyOutline /></NIcon></template>
                    </NButton>
                  </div>
                </li>
                <li>
                  <span class="fact-list__label">{{ t("system.onNetwork") }}</span>
                  <div class="fact-list__stack">
                    <div v-for="url in visibleLan" :key="url" class="fact-list__main">
                      <span class="fact-list__value or-mono">{{ url }}</span>
                      <NButton
                        quaternary
                        circle
                        size="small"
                        :aria-label="t('system.copy')"
                        @click="copyText(url, t('system.lan'))"
                      >
                        <template #icon><NIcon><CopyOutline /></NIcon></template>
                      </NButton>
                    </div>
                    <span v-if="!lanUrls.length" class="fact-list__value">{{ t("system.none") }}</span>
                    <button
                      v-if="hiddenLan > 0"
                      type="button"
                      class="fact-list__more"
                      @click="showAllLan = !showAllLan"
                    >
                      {{ showAllLan ? t("system.showLess") : t("system.showMore", { n: hiddenLan }) }}
                    </button>
                  </div>
                </li>
                <li>
                  <span class="fact-list__label">{{ t("system.browser") }}</span>
                  <span class="fact-list__value or-mono">{{ browserOrigin || "—" }}</span>
                </li>
              </ul>
            </SettingsSection>

            <SettingsSection :title="t('monitor.title')" :description="t('monitor.hint')">
              <ul class="fact-list">
                <li>
                  <span class="fact-list__label">{{ t("monitor.live") }}</span>
                  <div class="fact-list__main">
                    <span class="fact-list__value or-mono">{{ monitorBase }}/health/live</span>
                    <NButton
                      quaternary
                      circle
                      size="small"
                      :aria-label="t('system.copy')"
                      @click="copyText(`${monitorBase}/health/live`, t('monitor.live'))"
                    >
                      <template #icon><NIcon><CopyOutline /></NIcon></template>
                    </NButton>
                  </div>
                </li>
                <li>
                  <span class="fact-list__label">{{ t("monitor.ready") }}</span>
                  <div class="fact-list__main">
                    <span class="fact-list__value or-mono">{{ monitorBase }}/health/ready</span>
                    <NButton
                      quaternary
                      circle
                      size="small"
                      :aria-label="t('system.copy')"
                      @click="copyText(`${monitorBase}/health/ready`, t('monitor.ready'))"
                    >
                      <template #icon><NIcon><CopyOutline /></NIcon></template>
                    </NButton>
                  </div>
                </li>
                <li>
                  <span class="fact-list__label">{{ t("monitor.metrics") }}</span>
                  <div class="fact-list__main">
                    <span class="fact-list__value or-mono">{{ monitorBase }}/metrics</span>
                    <NButton
                      quaternary
                      circle
                      size="small"
                      :aria-label="t('system.copy')"
                      @click="copyText(`${monitorBase}/metrics`, t('monitor.metrics'))"
                    >
                      <template #icon><NIcon><CopyOutline /></NIcon></template>
                    </NButton>
                  </div>
                </li>
              </ul>
              <SettingRow :label="t('monitor.healthPublic')">
                <NSwitch v-model:value="draft.health_detail_public" />
                <template #hint>{{ t("monitor.healthPublicHint") }}</template>
              </SettingRow>
              <SettingRow stack :label="t('monitor.token')">
                <NInput
                  v-model:value="draft.metrics_token"
                  type="password"
                  show-password-on="click"
                  :placeholder="settings.metrics_token_set ? t('monitor.tokenPlaceholder') : ''"
                />
                <template #hint>{{ t("monitor.tokenHint") }}</template>
              </SettingRow>
              <NAlert v-if="draft.metrics_token.trim()" type="info" :bordered="false" style="margin-bottom: 12px">
                {{ t("monitor.tokenOnce") }}
                <div class="token-once">{{ draft.metrics_token }}</div>
              </NAlert>
              <NSpace>
                <NButton secondary @click="generateMetricsToken">{{ t("monitor.generate") }}</NButton>
                <NButton
                  v-if="settings.metrics_token_set || draft.metrics_token"
                  quaternary
                  @click="clearMetricsToken"
                >
                  {{ t("monitor.clear") }}
                </NButton>
              </NSpace>
            </SettingsSection>

            <SettingsSection :title="t('system.installTitle')" :description="t('system.installHint')">
              <ul class="fact-list">
                <li>
                  <span class="fact-list__label">{{ t("system.ui") }}</span>
                  <div>
                    <span class="fact-list__value">{{ webUiVersion }}</span>
                    <span v-if="buildRuntime && buildRuntime !== '—'" class="fact-list__meta">
                      {{ t("system.built") }} {{ buildRuntime }}
                    </span>
                  </div>
                </li>
                <li>
                  <span class="fact-list__label">{{ t("system.python") }}</span>
                  <span class="fact-list__value">{{ system.python_version }}</span>
                </li>
                <li>
                  <span class="fact-list__label">{{ t("system.platform") }}</span>
                  <div>
                    <span class="fact-list__value">{{ osSummary.name }}</span>
                    <span v-if="osSummary.detail" class="fact-list__meta">{{ osSummary.detail }}</span>
                  </div>
                </li>
                <li>
                  <span class="fact-list__label">{{ t("system.engine") }}</span>
                  <span class="fact-list__value">{{ inferenceBackendLabel }}</span>
                </li>
                <li>
                  <span class="fact-list__label">{{ t("system.models") }}</span>
                  <span class="fact-list__value or-mono">{{ settings.models_dir }}</span>
                </li>
                <li>
                  <span class="fact-list__label">{{ t("system.settingsFile") }}</span>
                  <span class="fact-list__value or-mono">{{
                    settings.runtime_settings_path || "data/runtime_settings.json"
                  }}</span>
                </li>
              </ul>
            </SettingsSection>

            <SettingsSection :title="t('system.lockedTitle')" :description="t('system.lockedHint')">
              <ul class="fact-list">
                <li>
                  <span class="fact-list__label">{{ t("system.auth") }}</span>
                  <div>
                    <span class="fact-list__value">{{
                      settings.auth_required ? t("system.authOn") : t("system.authOff")
                    }}</span>
                    <span class="fact-list__meta">OPENRECOGNITION_AUTH_REQUIRED</span>
                  </div>
                </li>
                <li>
                  <span class="fact-list__label">{{ t("system.web") }}</span>
                  <div>
                    <span class="fact-list__value">{{
                      settings.web_enabled ? t("system.enabled") : t("system.disabled")
                    }}</span>
                    <span class="fact-list__meta">OPENRECOGNITION_WEB_ENABLED</span>
                  </div>
                </li>
                <li>
                  <span class="fact-list__label">{{ t("system.docs") }}</span>
                  <div>
                    <span class="fact-list__value">{{
                      settings.docs_enabled ? t("system.enabled") : t("system.disabled")
                    }}</span>
                    <span class="fact-list__meta">OPENRECOGNITION_DOCS_ENABLED</span>
                  </div>
                </li>
                <li>
                  <span class="fact-list__label">{{ t("system.cors") }}</span>
                  <div>
                    <span class="fact-list__value">{{ system.web_origin || t("system.anyOrigin") }}</span>
                    <span class="fact-list__meta">OPENRECOGNITION_WEB_ORIGIN</span>
                  </div>
                </li>
                <li>
                  <span class="fact-list__label">{{ t("system.data") }}</span>
                  <div>
                    <span class="fact-list__value or-mono">{{ settings.data_dir }}</span>
                    <span class="fact-list__meta">OPENRECOGNITION_DATA_DIR</span>
                  </div>
                </li>
              </ul>
            </SettingsSection>
          </section>
        </div>
      </div>
      <StickySaveBar
        :dirty="dirty"
        :saving="saving"
        :can-save="!errorKey"
        @save="save"
        @discard="resetDraft"
      />
    </template>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 1040px;
}

.settings-shell {
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr);
  gap: 28px;
  align-items: start;
}

.settings-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  position: sticky;
  top: 12px;
}

.settings-nav__item {
  text-align: left;
  border: 0;
  background: transparent;
  border-radius: 8px;
  padding: 8px 12px;
  font: inherit;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--or-text-2);
  cursor: pointer;
}

.settings-nav__item:hover {
  background: var(--or-accent-tint);
  color: var(--or-text-1);
}

.settings-nav__item.is-active,
.settings-nav__item.is-active:hover {
  background: var(--or-accent);
  color: var(--or-on-accent);
  font-weight: 600;
}

.system-panel {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.system-panel :deep(.settings-section + .settings-section) {
  margin-top: 0;
}

.glance {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.glance__item {
  min-width: 0;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid var(--or-line);
  background: var(--or-surface);
}

.glance__item strong {
  display: block;
  margin-top: 6px;
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.fact-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.fact-list li {
  display: grid;
  grid-template-columns: 9.5rem minmax(0, 1fr);
  align-items: start;
  gap: 6px 18px;
  padding: 12px 0;
  border-bottom: 1px solid var(--or-line);
}

.fact-list li:first-child {
  padding-top: 0;
}

.fact-list li:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.fact-list__label {
  padding-top: 2px;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--or-text-2);
}

.fact-list__main,
.fact-list__stack {
  min-width: 0;
}

.fact-list__main {
  display: flex;
  align-items: center;
  gap: 2px;
}

.fact-list__stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.fact-list__value {
  font-size: 0.875rem;
  line-height: 1.4;
  color: var(--or-text-1);
  overflow-wrap: anywhere;
}

.fact-list__more {
  border: 0;
  background: transparent;
  padding: 0;
  font: inherit;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--or-accent);
  cursor: pointer;
}

.fact-list__meta {
  display: block;
  margin-top: 2px;
  font-family: var(--or-font-mono);
  font-size: 0.75rem;
  color: var(--or-text-3);
  overflow-wrap: anywhere;
}

.system-warn {
  margin: 0;
}

.token-once {
  margin-top: 6px;
  font-family: var(--or-font-mono);
  font-size: 0.8125rem;
  overflow-wrap: anywhere;
}

@media (max-width: 720px) {
  .glance {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .fact-list li {
    grid-template-columns: 1fr;
    gap: 2px;
  }

  .fact-list__label {
    padding-top: 0;
  }
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

.unit {
  font-size: 0.8125rem;
  color: var(--n-text-color-3);
}

@media (max-width: 800px) {
  .settings-shell {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .settings-nav {
    position: static;
    flex-direction: row;
    overflow-x: auto;
  }

  .settings-nav__item {
    white-space: nowrap;
  }
}
</style>
