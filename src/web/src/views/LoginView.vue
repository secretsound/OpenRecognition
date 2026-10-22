<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NForm, NFormItem, NInput, useMessage } from "naive-ui";
import type { FormInst, FormRules } from "naive-ui";
import { useAuth } from "@/composables/useAuth";
import { api, ApiError } from "@/api/client";
import { safeAppPath } from "@/utils/safeRedirect";
import LogoMark from "@/components/LogoMark.vue";
import { loadUiConfig, t, uiConfig } from "@/i18n";

const USER_KEY = "or-user";
const ROLE_KEY = "or-role";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const { login, setSession } = useAuth();

const formRef = ref<FormInst | null>(null);
const loading = ref(false);
const checking = ref(true);
const setupRequired = ref(false);
const model = ref({ username: "admin", password: "", confirm: "" });

const rules = computed<FormRules>(() => ({
  username: [{ required: true, message: t("login.userRequired"), trigger: "blur" }],
  password: [
    { required: true, message: t("login.passRequired"), trigger: "blur" },
    {
      validator: (_rule, value: string) => !setupRequired.value || value.length >= 8,
      message: t("login.passShort"),
      trigger: "blur",
    },
  ],
  confirm: [
    {
      validator: (_rule, value: string) => !setupRequired.value || value === model.value.password,
      message: t("login.mismatch"),
      trigger: "blur",
    },
  ],
}));

const strength = ref("");
function onPassword(v: string) {
  model.value.password = v;
  if (!setupRequired.value) return;
  if (v.length < 8) strength.value = t("login.passShort");
  else if (v.length < 12) strength.value = t("login.better");
  else strength.value = t("login.strong");
}

const nextPath = computed(() => safeAppPath(route.query.redirect) ?? "/");
const ssoHref = computed(
  () => `/v1/auth/sso/start?next=${encodeURIComponent(nextPath.value)}`,
);
const ssoError = computed(() => {
  const code = route.query.sso_error;
  if (code === "denied" || code === "failed" || code === "unprovisioned" || code === "invalid") {
    return t(`login.sso.${code}`);
  }
  return "";
});

onMounted(async () => {
  if (!uiConfig.value) {
    try {
      await loadUiConfig();
    } catch {
      /* English fallback */
    }
  }
  try {
    const status = await api<{ required: boolean }>("/v1/auth/setup", { skipAuthRedirect: true });
    setupRequired.value = status.required;
    if (!status.required) model.value.username = "";
  } catch {
    setupRequired.value = false;
    model.value.username = "";
  } finally {
    checking.value = false;
  }
});

async function onSubmit() {
  try {
    await formRef.value?.validate();
  } catch {
    return;
  }
  loading.value = true;
  try {
    const res = setupRequired.value
      ? await api<{ username: string; role: string }>("/v1/auth/setup", {
          method: "POST",
          json: { username: model.value.username.trim(), password: model.value.password },
        })
      : await login(model.value.username, model.value.password);
    setSession(res.username, res.role);
    sessionStorage.setItem(USER_KEY, res.username);
    sessionStorage.setItem(ROLE_KEY, res.role);
    message.success(t("login.welcome", { name: res.username }));
    router.push(nextPath.value);
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : t("login.failed"));
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <LogoMark :size="40" />
        <div>
          <h1 class="or-title">OpenRecognition</h1>
          <p v-if="setupRequired" class="or-muted">{{ t("login.setupLead") }}</p>
          <p v-else class="or-muted">{{ t("login.lead") }}</p>
        </div>
      </div>
      <p v-if="checking" class="or-muted or-small">{{ t("login.checking") }}</p>
      <template v-else>
      <p v-if="ssoError" class="login-error">{{ ssoError }}</p>
      <NForm ref="formRef" :model="model" :rules="rules" size="large" @submit.prevent="onSubmit">
        <NFormItem path="username" :label="t('login.username')">
          <NInput v-model:value="model.username" :placeholder="t('login.username')" autocomplete="username" />
        </NFormItem>
        <NFormItem path="password" :label="t('login.password')">
          <NInput
            :value="model.password"
            type="password"
            show-password-on="click"
            :placeholder="t('login.password')"
            :autocomplete="setupRequired ? 'new-password' : 'current-password'"
            @update:value="onPassword"
          />
          <p v-if="setupRequired && model.password" class="or-muted or-small" style="margin-top: 8px">
            {{ strength }}
          </p>
        </NFormItem>
        <NFormItem v-if="setupRequired" path="confirm" :label="t('login.confirm')">
          <NInput
            v-model:value="model.confirm"
            type="password"
            show-password-on="click"
            :placeholder="t('login.confirm')"
            autocomplete="new-password"
          />
        </NFormItem>
        <NButton type="primary" block attr-type="submit" :loading="loading">
          {{ setupRequired ? t("login.create") : t("login.signIn") }}
        </NButton>
      </NForm>
      </template>
      <div v-if="!checking && !setupRequired && uiConfig?.sso_enabled" class="sso-block">
        <p class="or-muted or-small sso-or">{{ t("login.or") }}</p>
        <NButton tag="a" :href="ssoHref" block secondary>{{ uiConfig.sso_label }}</NButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100%;
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--or-space-6);
  background: var(--or-bg);
}

.login-card {
  width: min(100%, 400px);
  padding: var(--or-space-8);
  border-radius: var(--or-radius-lg);
  background: var(--or-surface);
  border: 1px solid var(--or-line);
  box-shadow: var(--or-shadow);
}

.login-brand {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: var(--or-space-6);
}

.login-brand .or-title {
  font-size: var(--or-text-heading);
  margin-bottom: 6px;
}

.login-error {
  margin: 0 0 12px;
  color: var(--or-danger, #c2410c);
  font-size: 0.875rem;
}

.sso-block {
  margin-top: 14px;
}

.sso-or {
  text-align: center;
  margin: 0 0 10px;
}
</style>
