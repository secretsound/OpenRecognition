<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput, NSelect, NSpace, NSwitch, useMessage } from "naive-ui";
import { CopyOutline } from "@vicons/ionicons5";
import { NIcon } from "naive-ui";
import { api, ApiError } from "@/api/client";
import type { AppSettingsOut, OidcDiscoverOut, SamlMetadataOut } from "@/types/api";
import { callbackBase, type SettingsDraft } from "@/components/settings/settingsDraft";
import SettingsSection from "@/components/settings/SettingsSection.vue";
import SettingRow from "@/components/settings/SettingRow.vue";
import SegmentedControl from "@/components/kit/SegmentedControl.vue";
import { t } from "@/i18n";

const props = defineProps<{
  draft: SettingsDraft;
  settings: AppSettingsOut;
}>();

const message = useMessage();
const checking = ref(false);
const loadingMeta = ref(false);
const metaUrl = ref("");

const roles = computed(() => [
  { value: "viewer", label: t("role.viewer") },
  { value: "operator", label: t("role.operator") },
  { value: "admin", label: t("role.admin") },
]);

const protocols = computed(() => [
  { value: "oidc", label: t("sso.oidc") },
  { value: "saml", label: t("sso.saml") },
]);

const base = computed(() => callbackBase(props.draft.public_url));
const redirectUri = computed(() => `${base.value}/v1/auth/sso/oidc/callback`);
const acsUrl = computed(() => `${base.value}/v1/auth/sso/saml/acs`);
const metadataUrl = computed(() => `${base.value}/v1/auth/sso/saml/metadata`);
const spEntity = computed(() => props.draft.saml_sp_entity_id.trim() || metadataUrl.value);

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    message.success(t("settings.copied", { label: text }));
  } catch {
    message.error(t("settings.copyFailed"));
  }
}

async function checkIssuer() {
  checking.value = true;
  try {
    const out = await api<OidcDiscoverOut>("/v1/admin/sso/oidc/discover", {
      method: "POST",
      json: { issuer: props.draft.oidc_issuer.trim() },
    });
    props.draft.oidc_issuer = out.issuer;
    message.success(t("oidc.checked"));
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : t("settings.saveFailed"));
  } finally {
    checking.value = false;
  }
}

async function loadMetadata() {
  loadingMeta.value = true;
  try {
    const out = await api<SamlMetadataOut>("/v1/admin/sso/saml/metadata", {
      method: "POST",
      json: { url: metaUrl.value.trim() },
    });
    props.draft.saml_idp_entity_id = out.saml_idp_entity_id;
    props.draft.saml_idp_sso_url = out.saml_idp_sso_url;
    props.draft.saml_idp_x509_cert = out.saml_idp_x509_cert;
    message.success(t("saml.loaded"));
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : t("settings.saveFailed"));
  } finally {
    loadingMeta.value = false;
  }
}
</script>

<template>
  <SettingsSection :title="t('sso.title')" :description="t('sso.lead')">
    <SettingRow :label="t('sso.enable')">
      <NSwitch v-model:value="draft.sso_enabled" />
    </SettingRow>
    <SettingRow stack :label="t('sso.protocol')">
      <SegmentedControl v-model="draft.sso_protocol" :options="protocols" aria-label="SSO protocol" />
    </SettingRow>
    <SettingRow :label="t('sso.label')">
      <NInput v-model:value="draft.sso_label" style="width: 240px" maxlength="40" />
    </SettingRow>
    <SettingRow :label="t('sso.provision')">
      <NSwitch v-model:value="draft.sso_auto_provision" />
      <template #hint>{{ t("sso.provisionHint") }}</template>
    </SettingRow>
    <SettingRow :label="t('sso.role')">
      <NSelect v-model:value="draft.sso_default_role" :options="roles" style="width: 180px" />
    </SettingRow>
    <SettingRow :label="t('sso.link')">
      <NSwitch v-model:value="draft.sso_link_existing" />
      <template #hint>{{ t("sso.linkHint") }}</template>
    </SettingRow>
    <p class="note">{{ t("sso.groupsHint") }}</p>
  </SettingsSection>

  <SettingsSection v-if="draft.sso_protocol === 'oidc'" :title="t('sso.oidc')">
    <SettingRow stack :label="t('oidc.issuer')">
      <NSpace vertical :size="8" style="width: 100%">
        <NInput v-model:value="draft.oidc_issuer" placeholder="https://idp.example.com" />
        <NButton secondary :loading="checking" :disabled="!draft.oidc_issuer.trim()" @click="checkIssuer">
          {{ t("oidc.check") }}
        </NButton>
      </NSpace>
    </SettingRow>
    <SettingRow stack :label="t('oidc.clientId')">
      <NInput v-model:value="draft.oidc_client_id" />
    </SettingRow>
    <SettingRow stack :label="t('oidc.secret')">
      <NInput
        v-model:value="draft.oidc_client_secret"
        type="password"
        show-password-on="click"
        :placeholder="settings.oidc_client_secret_set ? t('oidc.secretPlaceholder') : t('oidc.secretEmpty')"
      />
    </SettingRow>
    <SettingRow v-if="settings.oidc_client_secret_set" :label="t('oidc.clear')">
      <NSwitch v-model:value="draft.clear_oidc_client_secret" />
    </SettingRow>
    <SettingRow stack :label="t('oidc.scopes')">
      <NInput v-model:value="draft.oidc_scopes" />
    </SettingRow>
    <SettingRow :label="t('sso.username')">
      <NInput v-model:value="draft.sso_username_claim" style="width: 220px" />
    </SettingRow>
    <SettingRow :label="t('oidc.groups')">
      <NInput v-model:value="draft.oidc_groups_claim" style="width: 220px" />
    </SettingRow>
    <SettingRow stack :label="t('sso.redirect')">
      <span class="copy-line">
        <code>{{ redirectUri }}</code>
        <NButton quaternary size="tiny" :aria-label="redirectUri" @click="copyText(redirectUri)">
          <template #icon><NIcon :component="CopyOutline" /></template>
        </NButton>
      </span>
    </SettingRow>
  </SettingsSection>

  <SettingsSection v-else :title="t('sso.saml')">
    <SettingRow stack :label="t('saml.metaUrl')">
      <NSpace vertical :size="8" style="width: 100%">
        <NInput v-model:value="metaUrl" placeholder="https://idp.example.com/metadata" />
        <NButton secondary :loading="loadingMeta" :disabled="metaUrl.trim().length < 8" @click="loadMetadata">
          {{ t("saml.load") }}
        </NButton>
      </NSpace>
    </SettingRow>
    <SettingRow stack :label="t('saml.entity')">
      <NInput v-model:value="draft.saml_idp_entity_id" />
    </SettingRow>
    <SettingRow stack :label="t('saml.ssoUrl')">
      <NInput v-model:value="draft.saml_idp_sso_url" />
    </SettingRow>
    <SettingRow stack :label="t('saml.cert')">
      <NInput v-model:value="draft.saml_idp_x509_cert" type="textarea" :autosize="{ minRows: 4, maxRows: 10 }" />
    </SettingRow>
    <SettingRow :label="t('saml.username')">
      <NInput v-model:value="draft.saml_username_attr" style="width: 220px" />
    </SettingRow>
    <SettingRow :label="t('saml.groups')">
      <NInput v-model:value="draft.saml_groups_attr" style="width: 220px" />
    </SettingRow>
    <SettingRow stack :label="t('sso.sp')">
      <NInput v-model:value="draft.saml_sp_entity_id" :placeholder="spEntity" />
      <template #hint>{{ t("saml.spHint") }}</template>
    </SettingRow>
    <SettingRow stack :label="t('sso.acs')">
      <span class="copy-line">
        <code>{{ acsUrl }}</code>
        <NButton quaternary size="tiny" @click="copyText(acsUrl)">
          <template #icon><NIcon :component="CopyOutline" /></template>
        </NButton>
      </span>
    </SettingRow>
    <SettingRow stack :label="t('sso.metadata')">
      <span class="copy-line">
        <code>{{ metadataUrl }}</code>
        <NButton quaternary size="tiny" @click="copyText(metadataUrl)">
          <template #icon><NIcon :component="CopyOutline" /></template>
        </NButton>
      </span>
    </SettingRow>
  </SettingsSection>
</template>

<style scoped>
.note {
  margin: 8px 0 0;
  font-size: 0.8rem;
  line-height: 1.45;
  color: var(--n-text-color-3);
}
.copy-line {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}
.copy-line code {
  font-size: 0.75rem;
  word-break: break-all;
}
</style>
