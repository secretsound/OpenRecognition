<script setup lang="ts">
import { computed, ref } from "vue";
import { NAlert, NButton, NInput, NInputNumber, NSpace, NSwitch, useMessage } from "naive-ui";
import { api, ApiError } from "@/api/client";
import type { AppSettingsOut, SelfSignedTlsOut } from "@/types/api";
import type { SettingsDraft } from "@/components/settings/settingsDraft";
import SettingsSection from "@/components/settings/SettingsSection.vue";
import SettingRow from "@/components/settings/SettingRow.vue";
import { t } from "@/i18n";
import { formatAbsolute, parseDate } from "@/utils/time";

const props = defineProps<{
  draft: SettingsDraft;
  settings: AppSettingsOut;
}>();

const message = useMessage();
const generating = ref(false);

const tlsLine = computed(() => {
  const subject = props.settings.tls_subject;
  if (!subject) return props.settings.tls_error || "";
  return t("network.tlsOk", {
    subject,
    expires: props.settings.tls_expires_at && parseDate(props.settings.tls_expires_at)
      ? formatAbsolute(props.settings.tls_expires_at)
      : props.settings.tls_expires_at || "—",
  });
});

async function generate() {
  const raw = props.draft.public_url.trim();
  let hostname = props.draft.host.trim() || "localhost";
  if (raw) {
    try {
      hostname = new URL(raw).hostname || hostname;
    } catch {
      hostname = raw.replace(/^https?:\/\//, "").split("/")[0].split(":")[0] || hostname;
    }
  }
  if (hostname === "0.0.0.0" || hostname === "::") {
    hostname = window.location.hostname || "localhost";
  }
  generating.value = true;
  try {
    const out = await api<SelfSignedTlsOut>("/v1/admin/tls/self-signed", {
      method: "POST",
      json: { hostname },
    });
    props.draft.tls_cert_pem = out.cert_pem;
    props.draft.tls_key_pem = out.key_pem;
    message.success(out.subject);
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : t("settings.saveFailed"));
  } finally {
    generating.value = false;
  }
}
</script>

<template>
  <SettingsSection :title="t('network.url')">
    <SettingRow stack :label="t('network.url')">
      <NInput v-model:value="draft.public_url" placeholder="https://recognize.example.com" />
      <template #hint>{{ t("network.urlHint") }}</template>
    </SettingRow>
    <SettingRow :label="t('network.proxy')">
      <NSwitch v-model:value="draft.behind_proxy" />
      <template #hint>{{ t("network.proxyHint") }}</template>
    </SettingRow>
    <SettingRow stack :label="t('network.trusted')">
      <NInput v-model:value="draft.trusted_proxies" placeholder="127.0.0.1, ::1" />
      <template #hint>{{ t("network.trustedHint") }}</template>
    </SettingRow>
  </SettingsSection>

  <SettingsSection :title="t('network.listeners')">
    <SettingRow :label="t('network.bind')">
      <NInput v-model:value="draft.host" style="width: 220px" />
      <template #hint>{{ t("network.bindHint") }}</template>
    </SettingRow>
    <SettingRow :label="t('network.http')">
      <NSpace align="center" :size="8">
        <NSwitch v-model:value="draft.http_enabled" />
        <NInputNumber v-model:value="draft.port" :min="1" :max="65535" style="width: 120px" />
      </NSpace>
    </SettingRow>
    <SettingRow :label="t('network.https')">
      <NSpace align="center" :size="8">
        <NSwitch v-model:value="draft.https_enabled" />
        <NInputNumber v-model:value="draft.https_port" :min="1" :max="65535" style="width: 120px" />
      </NSpace>
    </SettingRow>
    <NAlert v-if="tlsLine" :type="settings.tls_error ? 'warning' : 'success'" :bordered="false">
      {{ tlsLine }}
    </NAlert>
    <SettingRow stack :label="t('network.certFile')">
      <NInput v-model:value="draft.tls_cert_file" />
    </SettingRow>
    <SettingRow stack :label="t('network.keyFile')">
      <NInput v-model:value="draft.tls_key_file" />
    </SettingRow>
    <SettingRow stack :label="t('network.certPem')">
      <NInput v-model:value="draft.tls_cert_pem" type="textarea" :autosize="{ minRows: 4, maxRows: 8 }" />
      <template #hint>{{ t("network.pemHint") }}</template>
    </SettingRow>
    <SettingRow stack :label="t('network.keyPem')">
      <NInput v-model:value="draft.tls_key_pem" type="textarea" :autosize="{ minRows: 4, maxRows: 8 }" />
    </SettingRow>
    <NButton secondary :loading="generating" @click="generate">{{ t("network.generate") }}</NButton>
  </SettingsSection>
</template>
