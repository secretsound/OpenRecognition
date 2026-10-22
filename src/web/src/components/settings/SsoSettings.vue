<script setup lang="ts">
import { computed, ref } from "vue";
import { NButton, NInput, NSelect, NSwitch, useMessage } from "naive-ui";
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

const matchBy = computed(() => [
  { value: "username" as const, label: t("sso.matchUsername") },
  { value: "email" as const, label: t("sso.matchEmail") },
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
    <SettingRow :label="t('sso.label')">
      <NInput v-model:value="draft.sso_label" style="width: 240px" maxlength="40" />
      <template #hint>{{ t("sso.labelHint") }}</template>
    </SettingRow>
  </SettingsSection>

  <SettingsSection :title="t('sso.provider')" :description="t('sso.providerLead')">
    <SettingRow stack :label="t('sso.protocol')">
      <SegmentedControl v-model="draft.sso_protocol" :options="protocols" aria-label="SSO protocol" />
    </SettingRow>

    <p class="kicker">{{ t("sso.fromIdp") }}</p>
    <template v-if="draft.sso_protocol === 'oidc'">
      <SettingRow stack :label="t('oidc.issuer')">
        <div class="inline">
          <NInput v-model:value="draft.oidc_issuer" placeholder="https://idp.example.com" />
          <NButton secondary :loading="checking" :disabled="!draft.oidc_issuer.trim()" @click="checkIssuer">
            {{ t("oidc.check") }}
          </NButton>
        </div>
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
        <template #hint>{{ t("oidc.scopesHint") }}</template>
      </SettingRow>
      <p class="kicker">{{ t("sso.toIdp") }}</p>
      <SettingRow stack :label="t('sso.redirect')">
        <span class="copy-line">
          <code>{{ redirectUri }}</code>
          <NButton quaternary size="small" :aria-label="redirectUri" @click="copyText(redirectUri)">
            <template #icon><NIcon :component="CopyOutline" /></template>
            {{ t("sso.copy") }}
          </NButton>
        </span>
      </SettingRow>
    </template>
    <template v-else>
      <SettingRow stack :label="t('saml.metaUrl')">
        <div class="inline">
          <NInput v-model:value="metaUrl" placeholder="https://idp.example.com/metadata" />
          <NButton secondary :loading="loadingMeta" :disabled="metaUrl.trim().length < 8" @click="loadMetadata">
            {{ t("saml.load") }}
          </NButton>
        </div>
      </SettingRow>
      <SettingRow stack :label="t('saml.entity')">
        <NInput v-model:value="draft.saml_idp_entity_id" />
      </SettingRow>
      <SettingRow stack :label="t('saml.ssoUrl')">
        <NInput v-model:value="draft.saml_idp_sso_url" />
      </SettingRow>
      <SettingRow stack :label="t('saml.cert')">
        <NInput v-model:value="draft.saml_idp_x509_cert" type="textarea" :autosize="{ minRows: 4, maxRows: 8 }" />
      </SettingRow>
      <p class="kicker">{{ t("sso.toIdp") }}</p>
      <SettingRow stack :label="t('sso.sp')">
        <NInput v-model:value="draft.saml_sp_entity_id" :placeholder="spEntity" />
        <template #hint>{{ t("saml.spHint") }}</template>
      </SettingRow>
      <SettingRow stack :label="t('sso.acs')">
        <span class="copy-line">
          <code>{{ acsUrl }}</code>
          <NButton quaternary size="small" :aria-label="acsUrl" @click="copyText(acsUrl)">
            <template #icon><NIcon :component="CopyOutline" /></template>
            {{ t("sso.copy") }}
          </NButton>
        </span>
        <template #hint>{{ t("sso.acsHint") }}</template>
      </SettingRow>
      <SettingRow stack :label="t('sso.metadata')">
        <span class="copy-line">
          <code>{{ metadataUrl }}</code>
          <NButton quaternary size="small" :aria-label="metadataUrl" @click="copyText(metadataUrl)">
            <template #icon><NIcon :component="CopyOutline" /></template>
            {{ t("sso.copy") }}
          </NButton>
        </span>
      </SettingRow>
    </template>
  </SettingsSection>

  <SettingsSection :title="t('sso.accounts')" :description="t('sso.accountsLead')">
    <p class="kicker">{{ t("sso.newAccounts") }}</p>
    <SettingRow :label="t('sso.provision')">
      <NSwitch v-model:value="draft.sso_auto_provision" />
      <template #hint>{{ t("sso.provisionHint") }}</template>
    </SettingRow>
    <SettingRow v-if="draft.sso_auto_provision" :label="t('sso.role')">
      <NSelect v-model:value="draft.sso_default_role" :options="roles" style="width: 180px" />
    </SettingRow>

    <p class="kicker">{{ t("sso.knownAccounts") }}</p>
    <SettingRow :label="t('sso.link')">
      <NSwitch v-model:value="draft.sso_link_existing" />
      <template #hint>{{ t("sso.linkHint") }}</template>
    </SettingRow>
    <SettingRow v-if="draft.sso_link_existing" stack :label="t('sso.match')">
      <SegmentedControl v-model="draft.sso_match" :options="matchBy" :aria-label="t('sso.match')" />
      <template #hint>{{ t("sso.matchHint") }}</template>
    </SettingRow>
    <SettingRow v-if="draft.sso_protocol === 'oidc'" :label="t('sso.username')">
      <NInput v-model:value="draft.sso_username_claim" style="width: 220px" />
      <template #hint>
        {{ draft.sso_link_existing && draft.sso_match === "email" ? t("sso.usernameEmailHint") : t("sso.usernameHint") }}
      </template>
    </SettingRow>
    <SettingRow v-else :label="t('saml.username')">
      <NInput v-model:value="draft.saml_username_attr" style="width: 220px" />
      <template #hint>{{ t("saml.usernameHint") }}</template>
    </SettingRow>
    <SettingRow v-if="draft.sso_protocol === 'oidc'" :label="t('oidc.groups')">
      <NInput v-model:value="draft.oidc_groups_claim" style="width: 220px" />
      <template #hint>{{ t("sso.groupsHint") }}</template>
    </SettingRow>
    <SettingRow v-else :label="t('saml.groups')">
      <NInput v-model:value="draft.saml_groups_attr" style="width: 220px" />
      <template #hint>{{ t("sso.groupsHint") }}</template>
    </SettingRow>
  </SettingsSection>
</template>

<style scoped>
.kicker {
  margin: 18px 0 0;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--n-text-color-3);
}

.inline {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.inline :deep(.n-input) {
  flex: 1;
  min-width: 0;
}

.copy-line {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 36px;
  padding: 6px 6px 6px 12px;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  background: color-mix(in srgb, var(--n-text-color-3) 8%, transparent);
}

.copy-line code {
  flex: 1;
  min-width: 0;
  font-size: 0.8125rem;
  line-height: 1.4;
  word-break: break-all;
}
</style>
