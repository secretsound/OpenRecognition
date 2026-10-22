<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NForm, NFormItem, NInput, useMessage } from "naive-ui";
import type { FormInst, FormRules } from "naive-ui";
import { useAuth } from "@/composables/useAuth";
import { api, ApiError } from "@/api/client";
import { safeAppPath } from "@/utils/safeRedirect";
import LogoMark from "@/components/LogoMark.vue";

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

const rules: FormRules = {
  username: [{ required: true, message: "Username is required", trigger: "blur" }],
  password: [
    { required: true, message: "Password is required", trigger: "blur" },
    {
      validator: (_rule, value: string) => !setupRequired.value || value.length >= 8,
      message: "Use at least 8 characters",
      trigger: "blur",
    },
  ],
  confirm: [
    {
      validator: (_rule, value: string) => !setupRequired.value || value === model.value.password,
      message: "Passwords do not match",
      trigger: "blur",
    },
  ],
};

const strength = ref("");
function onPassword(v: string) {
  model.value.password = v;
  if (!setupRequired.value) return;
  if (v.length < 8) strength.value = "Use at least 8 characters";
  else if (v.length < 12) strength.value = "Okay — longer is better";
  else strength.value = "Strong enough for this server";
}

onMounted(async () => {
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
    message.success(`Welcome, ${res.username}`);
    router.push(safeAppPath(route.query.redirect) ?? "/");
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Sign in failed");
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
          <p v-if="setupRequired" class="or-muted">
            Create the admin account for this server. It is stored in the database on this machine.
          </p>
          <p v-else class="or-muted">
            Enroll people, pets, objects, and sounds, then recognize them from audio, photos, or video.
          </p>
        </div>
      </div>
      <p v-if="checking" class="or-muted or-small">Checking this server…</p>
      <NForm v-else ref="formRef" :model="model" :rules="rules" size="large" @submit.prevent="onSubmit">
        <NFormItem path="username" label="Username">
          <NInput v-model:value="model.username" placeholder="Username" autocomplete="username" />
        </NFormItem>
        <NFormItem path="password" label="Password">
          <NInput
            :value="model.password"
            type="password"
            show-password-on="click"
            placeholder="Password"
            :autocomplete="setupRequired ? 'new-password' : 'current-password'"
            @update:value="onPassword"
          />
          <p v-if="setupRequired && model.password" class="or-muted or-small" style="margin-top: 8px">
            {{ strength }}
          </p>
        </NFormItem>
        <NFormItem v-if="setupRequired" path="confirm" label="Confirm password">
          <NInput
            v-model:value="model.confirm"
            type="password"
            show-password-on="click"
            placeholder="Confirm password"
            autocomplete="new-password"
          />
        </NFormItem>
        <NButton type="primary" block attr-type="submit" :loading="loading">
          {{ setupRequired ? "Create account" : "Sign in" }}
        </NButton>
      </NForm>
      <p v-if="!checking && !setupRequired" class="or-muted or-small" style="margin-top: 16px">
        Use the admin account for this server.
      </p>
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
</style>
