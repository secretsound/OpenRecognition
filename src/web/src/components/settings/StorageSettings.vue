<script setup lang="ts">
import { onMounted, ref } from "vue";
import { NInput, NInputNumber, NSpace } from "naive-ui";
import { api } from "@/api/client";
import type { AppSettingsOut, StorageUsageOut } from "@/types/api";
import type { SettingsDraft } from "@/components/settings/settingsDraft";
import SettingsSection from "@/components/settings/SettingsSection.vue";
import SettingRow from "@/components/settings/SettingRow.vue";
import { t } from "@/i18n";
import { formatBytes } from "@/utils/time";

defineProps<{
  draft: SettingsDraft;
  settings: AppSettingsOut;
}>();

const usage = ref<StorageUsageOut | null>(null);

function bytes(value: number | undefined): string {
  if (value == null) return "—";
  if (value <= 0) return "0 B";
  return formatBytes(value);
}

async function loadUsage() {
  try {
    usage.value = await api<StorageUsageOut>("/v1/admin/storage-usage");
  } catch {
    usage.value = null;
  }
}

onMounted(loadUsage);
</script>

<template>
  <SettingsSection :title="t('settings.section.storage')" :description="t('storage.note')">
    <SettingRow stack :label="t('storage.models')">
      <NInput v-model:value="draft.models_dir" />
    </SettingRow>
    <SettingRow stack :label="t('storage.packs')">
      <NInput v-model:value="draft.model_packs_dir" />
    </SettingRow>
    <SettingRow stack :label="t('storage.data')">
      <NInput :value="settings.data_dir" disabled />
      <template #hint>{{ t("storage.dataHint") }}</template>
    </SettingRow>
    <SettingRow :label="t('storage.upload')">
      <NSpace align="center" :size="8">
        <NInputNumber v-model:value="draft.video_max_upload_mb" :min="1" :max="2048" style="width: 120px" />
        <span class="unit">{{ t("logs.mb") }}</span>
      </NSpace>
      <template #hint>{{ t("storage.uploadHint") }}</template>
    </SettingRow>
  </SettingsSection>

  <SettingsSection :title="t('storage.usage')" :description="t('storage.usageHint')">
    <ul class="usage">
      <li><span>{{ t("storage.usageData") }}</span><strong>{{ bytes(usage?.data_bytes) }}</strong></li>
      <li><span>{{ t("storage.usageModels") }}</span><strong>{{ bytes(usage?.models_bytes) }}</strong></li>
      <li><span>{{ t("storage.usageLogs") }}</span><strong>{{ bytes(usage?.logs_bytes) }}</strong></li>
    </ul>
  </SettingsSection>
</template>

<style scoped>
.unit {
  font-size: 0.8125rem;
  color: var(--n-text-color-3);
}
.usage {
  list-style: none;
  margin: 0;
  padding: 0;
}
.usage li {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid var(--or-line);
}
.usage li:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}
</style>
