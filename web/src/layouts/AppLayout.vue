<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NLayout,
  NLayoutHeader,
  NLayoutSider,
  NLayoutContent,
  NMenu,
  NButton,
  NTag,
  NDropdown,
  NDrawer,
  NIcon,
  NSpace,
  NBreadcrumb,
  NBreadcrumbItem,
  NTooltip,
} from "naive-ui";
import type { MenuOption } from "naive-ui";
import {
  HomeOutline,
  PeopleOutline,
  CameraOutline,
  PulseOutline,
  LinkOutline,
  PeopleCircleOutline,
  KeyOutline,
  SettingsOutline,
  HardwareChipOutline,
  SunnyOutline,
  MoonOutline,
  MenuOutline,
  LogOutOutline,
  ChevronBackOutline,
} from "@vicons/ionicons5";
import { api } from "@/api/client";
import { useAuth } from "@/composables/useAuth";
import { useTheme } from "@/composables/useTheme";
import { useSiderCollapsed } from "@/composables/useSiderCollapsed";
import { provideBreadcrumbTail } from "@/composables/useBreadcrumbTail";
import type { CapabilitiesOut } from "@/types/api";
import LogoMark from "@/components/LogoMark.vue";

const route = useRoute();
const router = useRouter();
const { username, role, logout, clearSession } = useAuth();
const { isDark, toggle } = useTheme();
const { collapsed, setCollapsed, restoreDesktopPreference } = useSiderCollapsed();

const mobileOpen = ref(false);
const capabilities = ref<CapabilitiesOut | null>(null);
const isMobile = ref(false);
const { tail: breadcrumbTail, override: breadcrumbOverride } = provideBreadcrumbTail();

function menuIcon(Icon: typeof PeopleOutline) {
  return () => h(NIcon, null, { default: () => h(Icon) });
}

const menuOptions = computed<MenuOption[]>(() => {
  const recognize: MenuOption[] = [
    { label: "Home", key: "/", icon: menuIcon(HomeOutline) },
    { label: "Library", key: "/enrollments", icon: menuIcon(PeopleOutline) },
    { label: "Try a match", key: "/test", icon: menuIcon(CameraOutline) },
  ];
  const manage: MenuOption[] = [
    { label: "Activity", key: "/logs", icon: menuIcon(PulseOutline) },
    { label: "Connections", key: "/integrations", icon: menuIcon(LinkOutline) },
    { label: "Users", key: "/users", icon: menuIcon(PeopleCircleOutline) },
    { label: "API keys", key: "/keys", icon: menuIcon(KeyOutline) },
  ];
  if (role.value === "admin") {
    manage.push({
      label: "Models",
      key: "/models",
      icon: menuIcon(HardwareChipOutline),
    });
  }
  manage.push({
    label: "Settings",
    key: "/settings",
    icon: menuIcon(SettingsOutline),
  });

  if (collapsed.value) {
    return [...recognize, ...manage];
  }
  return [
    { type: "group", label: "Recognize", key: "group-recognize", children: recognize },
    { type: "group", label: "Manage", key: "group-manage", children: manage },
  ];
});

const activeKey = computed(() => {
  const p = route.path;
  if (p === "/") return "/";
  if (p.startsWith("/enrollments")) return "/enrollments";
  if (p.startsWith("/test")) return "/test";
  if (p.startsWith("/users")) return "/users";
  if (p.startsWith("/keys")) return "/keys";
  if (p.startsWith("/integrations") || p.startsWith("/webhooks")) return "/integrations";
  if (p.startsWith("/logs")) return "/logs";
  if (p.startsWith("/models")) return "/models";
  if (p.startsWith("/settings")) return "/settings";
  return p;
});

const headerBreadcrumbs = computed(() => {
  if (breadcrumbOverride.value?.length) return breadcrumbOverride.value;
  const meta = route.meta.breadcrumbs;
  if (!meta?.length) return [];
  const items = meta.map((c) => ({ ...c }));
  if (breadcrumbTail.value && items.length) {
    items[items.length - 1] = { ...items[items.length - 1], label: breadcrumbTail.value };
  }
  return items;
});

const showBreadcrumbs = computed(() => headerBreadcrumbs.value.length >= 2);

const headerBackTo = computed(() => {
  const explicit = route.meta.backTo as string | undefined;
  if (explicit) return explicit;
  if (route.name === "enrollment-training" && route.params.id) {
    return `/enrollments/${route.params.id}`;
  }
  if (breadcrumbOverride.value && breadcrumbOverride.value.length >= 2) {
    const parent = breadcrumbOverride.value[breadcrumbOverride.value.length - 2];
    if (parent.to) return parent.to;
  }
  const crumbs = route.meta.breadcrumbs;
  if (!crumbs?.length || crumbs.length < 2) return null;
  return crumbs[0].to ?? null;
});

const headerBackLabel = computed(
  () => route.meta.breadcrumbs?.[0]?.label ?? "Back",
);

const packTooltip = computed(() => {
  if (!capabilities.value) return "";
  const models = Object.keys(capabilities.value.models ?? {}).join(", ") || "—";
  return `Active pack: ${capabilities.value.pack}\nModels: ${models}`;
});

const userOptions = [
  {
    label: "Logout",
    key: "logout",
    icon: () => h(NIcon, null, { default: () => h(LogOutOutline) }),
  },
];

function onMenuSelect(key: string) {
  router.push(key);
  mobileOpen.value = false;
}

async function handleUserAction(key: string) {
  if (key === "logout") {
    await logout();
    router.push("/login");
  }
}

onMounted(async () => {
  const mq = window.matchMedia("(max-width: 768px)");
  const update = () => {
    isMobile.value = mq.matches;
    if (mq.matches) {
      setCollapsed(true, false);
    } else {
      restoreDesktopPreference();
    }
  };
  update();
  mq.addEventListener("change", update);
  try {
    capabilities.value = await api<CapabilitiesOut>("/v1/capabilities");
  } catch {
    clearSession();
    router.push("/login");
  }
});
</script>

<template>
  <NLayout has-sider class="app-shell" :class="{ dark: isDark }">
    <NLayoutSider
      v-if="!isMobile"
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="240"
      v-model:collapsed="collapsed"
      show-trigger
      class="app-sider"
    >
      <div class="sider-inner">
        <div class="sider-brand" :class="{ collapsed }">
          <LogoMark :size="32" class="logo" />
          <span v-if="!collapsed" class="brand-name">OpenRecognition</span>
        </div>
        <NMenu
          class="sider-menu"
          :value="activeKey"
          :collapsed="collapsed"
          :collapsed-width="64"
          :options="menuOptions"
          @update:value="onMenuSelect"
        />
        <div v-if="capabilities" class="sider-footer" :class="{ collapsed }">
          <NTooltip trigger="hover" :disabled="!collapsed">
            <template #trigger>
              <NTag size="small" :bordered="false" type="success" class="sider-pack-tag">
                <span v-if="collapsed" class="sider-pack-short">{{
                  capabilities.pack.slice(0, 1)
                }}</span>
                <span v-else>{{ capabilities.pack }} pack</span>
              </NTag>
            </template>
            {{ packTooltip }}
          </NTooltip>
          <span v-if="!collapsed" class="sider-version">v{{ capabilities.version }}</span>
          <NTooltip v-else trigger="hover">
            <template #trigger>
              <span class="sider-version sider-version--collapsed">v{{ capabilities.version }}</span>
            </template>
            OpenRecognition v{{ capabilities.version }}
          </NTooltip>
        </div>
      </div>
    </NLayoutSider>

    <NDrawer v-model:show="mobileOpen" :width="260" placement="left">
      <div class="drawer-inner">
        <div class="sider-brand">
          <LogoMark :size="32" class="logo" />
          <span class="brand-name">OpenRecognition</span>
        </div>
        <NMenu :value="activeKey" :options="menuOptions" @update:value="onMenuSelect" />
        <div v-if="capabilities" class="sider-footer">
          <NTooltip trigger="hover">
            <template #trigger>
              <NTag size="small" :bordered="false" type="success">
                {{ capabilities.pack }} pack
              </NTag>
            </template>
            {{ packTooltip }}
          </NTooltip>
          <span class="sider-version">v{{ capabilities.version }}</span>
        </div>
      </div>
    </NDrawer>

    <NLayout class="app-main">
      <NLayoutHeader bordered class="app-header">
        <NSpace align="center" :size="12" class="header-left">
          <NButton
            v-if="isMobile"
            quaternary
            circle
            aria-label="Open menu"
            @click="mobileOpen = true"
          >
            <template #icon>
              <NIcon><MenuOutline /></NIcon>
            </template>
          </NButton>
          <NButton
            v-if="headerBackTo"
            quaternary
            circle
            class="header-back"
            :aria-label="`Back to ${headerBackLabel}`"
            @click="router.push(headerBackTo)"
          >
            <template #icon>
              <NIcon><ChevronBackOutline /></NIcon>
            </template>
          </NButton>
          <NBreadcrumb v-if="showBreadcrumbs" class="header-breadcrumb">
            <NBreadcrumbItem
              v-for="(crumb, i) in headerBreadcrumbs"
              :key="i"
              :clickable="!!crumb.to && i < headerBreadcrumbs.length - 1"
              @click="crumb.to && i < headerBreadcrumbs.length - 1 ? router.push(crumb.to) : undefined"
            >
              {{ crumb.label }}
            </NBreadcrumbItem>
          </NBreadcrumb>
        </NSpace>
        <NSpace align="center" :size="8">
          <NButton
            quaternary
            circle
            :aria-label="isDark ? 'Light mode' : 'Dark mode'"
            @click="toggle"
          >
            <template #icon>
              <NIcon><component :is="isDark ? SunnyOutline : MoonOutline" /></NIcon>
            </template>
          </NButton>
          <a href="/docs" target="_blank" rel="noopener" class="header-link">API</a>
          <NDropdown :options="userOptions" @select="handleUserAction">
            <NButton quaternary>{{ username ?? "User" }}</NButton>
          </NDropdown>
        </NSpace>
      </NLayoutHeader>
      <NLayoutContent class="app-page-bg" :class="{ dark: isDark }">
        <div class="content-container">
          <RouterView v-slot="{ Component }">
            <Transition name="fade" mode="out-in">
              <component :is="Component" />
            </Transition>
          </RouterView>
        </div>
      </NLayoutContent>
    </NLayout>
  </NLayout>
</template>

<style scoped>
.app-shell {
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

/* has-sider: keep sider + main in one flex row (requires static sider, not absolute) */
.app-shell > :deep(.n-layout-scroll-container) {
  display: flex;
  flex-wrap: nowrap;
  height: 100%;
  min-height: 0;
}

.app-sider {
  flex-shrink: 0;
}

.app-sider :deep(.n-layout-sider-scroll-container) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sider-inner,
.drawer-inner {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  height: 100%;
}

.drawer-inner {
  min-height: 100vh;
  padding-bottom: 16px;
}

.sider-menu {
  flex: 1;
  min-height: 0;
}

.sider-footer {
  flex-shrink: 0;
  margin-top: auto;
  padding: 12px 16px 16px;
  border-top: 1px solid var(--n-border-color);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.sider-footer.collapsed {
  align-items: center;
  padding: 12px 8px 16px;
}

.sider-pack-tag {
  max-width: 100%;
}

.sider-pack-short {
  font-weight: 600;
  text-transform: uppercase;
}

.sider-version {
  font-size: 0.75rem;
  color: var(--n-text-color-3);
  font-variant-numeric: tabular-nums;
}

.sider-version--collapsed {
  font-size: 0.65rem;
  max-width: 48px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.app-main :deep(.n-layout-scroll-container) {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.app-header {
  flex-shrink: 0;
  z-index: 2;
  position: relative;
}

.app-page-bg {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.app-page-bg :deep(.n-layout-scroll-container) {
  min-height: min-content;
}

.sider-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 16px;
  font-weight: 600;
  font-size: 1rem;
}

.sider-brand.collapsed {
  justify-content: center;
  padding: 20px 8px;
}

.logo {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
}

.brand-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 56px;
}

.header-left {
  flex: 1;
  min-width: 0;
}

.header-back {
  flex-shrink: 0;
}

.header-breadcrumb {
  min-width: 0;
}

.header-link {
  color: var(--n-text-color-2);
  text-decoration: none;
  font-size: 0.875rem;
}

.header-link:hover {
  color: var(--n-primary-color);
}
</style>
