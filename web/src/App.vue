<script setup lang="ts">
import { computed, onMounted } from "vue";
import {
  NConfigProvider,
  NMessageProvider,
  NNotificationProvider,
  NDialogProvider,
  enUS,
  dateEnUS,
} from "naive-ui";
import { useTheme } from "@/composables/useTheme";
import { useAuth } from "@/composables/useAuth";

const { naiveTheme, overrides, isDark } = useTheme();
const { setSession } = useAuth();

const themeClass = computed(() => (isDark.value ? "dark" : ""));

onMounted(() => {
  const user = sessionStorage.getItem("or-user");
  const role = sessionStorage.getItem("or-role");
  if (user && role) setSession(user, role);
});
</script>

<template>
  <NConfigProvider
    :theme="naiveTheme"
    :theme-overrides="overrides"
    :locale="enUS"
    :date-locale="dateEnUS"
    :class="themeClass"
  >
    <NMessageProvider>
      <NNotificationProvider>
        <NDialogProvider>
          <RouterView />
        </NDialogProvider>
      </NNotificationProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>
