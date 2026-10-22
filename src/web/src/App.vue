<script setup lang="ts">
import { onMounted } from "vue";
import {
  NConfigProvider,
  NMessageProvider,
  NNotificationProvider,
  NDialogProvider,
} from "naive-ui";
import { useTheme } from "@/composables/useTheme";
import { useAuth } from "@/composables/useAuth";
import { api } from "@/api/client";
import type { AuthMeOut } from "@/types/api";
import { roleFromScopes } from "@/utils/roles";
import { loadUiConfig, naiveDateLocale, naiveLocale } from "@/i18n";

const { naiveTheme, overrides } = useTheme();
const { setSession } = useAuth();

onMounted(async () => {
  try {
    await loadUiConfig();
  } catch {
    /* login and the shell still work in English */
  }
  const storedUser = sessionStorage.getItem("or-user");
  const storedRole = sessionStorage.getItem("or-role");
  if (storedUser && storedRole) setSession(storedUser, storedRole);
  try {
    const me = await api<AuthMeOut>("/v1/auth/me", { skipAuthRedirect: true });
    if (me.credential_type === "session" && me.name) {
      const role = me.role || roleFromScopes(me.scopes);
      setSession(me.name, role);
      sessionStorage.setItem("or-user", me.name);
      sessionStorage.setItem("or-role", role);
    }
  } catch {
    /* public pages and expired sessions fall through to the router guard */
  }
});
</script>

<template>
  <NConfigProvider
    :theme="naiveTheme"
    :theme-overrides="overrides"
    :locale="naiveLocale"
    :date-locale="naiveDateLocale"
    inline-theme-disabled
  >
    <NMessageProvider placement="bottom" :max="3">
      <NNotificationProvider placement="bottom-right" :max="3">
        <NDialogProvider>
          <RouterView />
        </NDialogProvider>
      </NNotificationProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>
