<script setup lang="ts">
import { ref } from "vue";
import { NButton, NPopconfirm, NSpace, useMessage } from "naive-ui";
import { api, apiForm, ApiError } from "@/api/client";
import type { BackupRestoreOut, ServiceRestartOut } from "@/types/api";
import SettingsSection from "@/components/settings/SettingsSection.vue";
import SettingRow from "@/components/settings/SettingRow.vue";
import { t } from "@/i18n";

const message = useMessage();
const downloading = ref(false);
const restoring = ref(false);
const chosen = ref<File | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);

async function download() {
  downloading.value = true;
  try {
    const res = await fetch("/v1/admin/backup", { credentials: "include" });
    if (!res.ok) throw new Error(t("storage.backupFailed"));
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "openrecognition-backup.zip";
    link.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    message.error(e instanceof Error ? e.message : t("storage.backupFailed"));
  } finally {
    downloading.value = false;
  }
}

function stage(event: Event) {
  const input = event.target as HTMLInputElement;
  chosen.value = input.files?.[0] ?? null;
}

async function restore() {
  if (!chosen.value) return;
  restoring.value = true;
  try {
    const form = new FormData();
    form.append("file", chosen.value);
    form.append("confirm", "restore");
    await apiForm<BackupRestoreOut>("/v1/admin/backup/restore", form);
    message.success(t("storage.restored"));
    try {
      await api<ServiceRestartOut>("/v1/admin/restart", { method: "POST" });
    } catch {
      /* the process leaves as soon as the restart is accepted */
    }
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : t("storage.restoreFailed"));
  } finally {
    restoring.value = false;
    chosen.value = null;
    if (fileInput.value) fileInput.value.value = "";
  }
}
</script>

<template>
  <SettingsSection :title="t('storage.backup')" :description="t('storage.backupHint')">
    <SettingRow :label="t('storage.download')">
      <NButton :loading="downloading" @click="download">{{ t("storage.download") }}</NButton>
    </SettingRow>
    <SettingRow :label="t('storage.restore')" stack>
      <NSpace align="center" :size="8">
        <input ref="fileInput" class="file" type="file" accept=".zip,application/zip" @change="stage" />
        <NButton @click="fileInput?.click()">{{ t("storage.choose") }}</NButton>
        <span v-if="chosen" class="file-name">{{ chosen.name }}</span>
        <NPopconfirm
          :positive-text="t('storage.restore')"
          :negative-text="t('settings.cancel')"
          @positive-click="restore"
        >
          <template #trigger>
            <NButton type="error" secondary :disabled="!chosen" :loading="restoring">
              {{ t("storage.restore") }}
            </NButton>
          </template>
          {{ t("storage.restoreConfirm") }}
        </NPopconfirm>
      </NSpace>
      <template #hint>{{ t("storage.restoreHint") }}</template>
    </SettingRow>
  </SettingsSection>
</template>

<style scoped>
.file {
  display: none;
}
.file-name {
  font-size: 0.8125rem;
  color: var(--n-text-color-2);
  overflow-wrap: anywhere;
}
</style>
