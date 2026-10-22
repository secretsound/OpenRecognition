<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { NButton, NInput, NInputNumber, NSelect, NSpace, NSwitch, useMessage } from "naive-ui";
import { api, ApiError } from "@/api/client";
import type { ServerLogsOut } from "@/types/api";
import type { SettingsDraft } from "@/components/settings/settingsDraft";
import SettingsSection from "@/components/settings/SettingsSection.vue";
import SettingRow from "@/components/settings/SettingRow.vue";
import { t } from "@/i18n";

defineProps<{ draft: SettingsDraft; logFile: string }>();

const router = useRouter();
const message = useMessage();
const lines = ref<string[]>([]);
const path = ref("");
const loading = ref(false);

const levels = computed(() => [
  { value: "debug", label: t("log.debug") },
  { value: "info", label: t("log.info") },
  { value: "warning", label: t("log.warning") },
  { value: "error", label: t("log.error") },
]);

async function refresh() {
  loading.value = true;
  try {
    const out = await api<ServerLogsOut>("/v1/admin/server-logs");
    lines.value = out.lines;
    path.value = out.path;
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : t("settings.loadFailed"));
  } finally {
    loading.value = false;
  }
}

onMounted(refresh);
</script>

<template>
  <SettingsSection :title="t('settings.section.logs')">
    <SettingRow :label="t('logs.level')">
      <NSelect v-model:value="draft.log_level" :options="levels" style="width: 180px" />
    </SettingRow>
    <SettingRow :label="t('logs.toFile')">
      <NSwitch v-model:value="draft.log_to_file" />
      <template #hint>{{ t("logs.toFileHint") }}</template>
    </SettingRow>
    <SettingRow :label="t('logs.max')">
      <NSpace align="center" :size="8">
        <NInputNumber v-model:value="draft.log_max_mb" :min="1" :max="200" style="width: 120px" />
        <span class="unit">{{ t("logs.mb") }}</span>
      </NSpace>
      <template #hint>{{ t("logs.maxHint") }}</template>
    </SettingRow>
    <SettingRow :label="t('logs.keep')">
      <NInputNumber v-model:value="draft.log_backup_count" :min="1" :max="30" style="width: 120px" />
      <template #hint>{{ t("logs.keepHint") }}</template>
    </SettingRow>
    <SettingRow stack :label="t('logs.dir')">
      <NInput v-model:value="draft.logs_dir" :placeholder="t('logs.dirHint')" />
      <template #hint>{{ t("logs.dirHint") }}</template>
    </SettingRow>
    <SettingRow v-if="logFile || path" stack :label="t('logs.file')">
      <code class="mono">{{ path || logFile }}</code>
    </SettingRow>
  </SettingsSection>
  <SettingsSection :title="t('logs.file')">
    <NSpace justify="space-between" align="center">
      <span class="hint">{{ t("logs.activity") }}</span>
      <NSpace>
        <NButton secondary @click="router.push('/logs')">{{ t("logs.openActivity") }}</NButton>
        <NButton :loading="loading" @click="refresh">{{ t("logs.refresh") }}</NButton>
      </NSpace>
    </NSpace>
    <pre class="log-tail">{{ lines.length ? lines.join("\n") : t("logs.empty") }}</pre>
  </SettingsSection>
</template>

<style scoped>
.hint,
.unit {
  font-size: 0.8125rem;
  color: var(--n-text-color-3);
}
.mono {
  font-size: 0.75rem;
  word-break: break-all;
}
.log-tail {
  margin: 12px 0 0;
  max-height: 320px;
  overflow: auto;
  padding: 12px;
  border-radius: 8px;
  background: var(--n-action-color);
  font-size: 0.75rem;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
