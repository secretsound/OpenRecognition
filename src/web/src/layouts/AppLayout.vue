<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NLayout,
  NLayoutSider,
  NLayoutContent,
  NMenu,
  NButton,
  NDropdown,
  NDrawer,
  NIcon,
  NTooltip,
} from "naive-ui";
import type { MenuOption } from "naive-ui";
import {
  HomeOutline,
  PeopleOutline,
  ScanOutline,
  PulseOutline,
  LinkOutline,
  PeopleCircleOutline,
  KeyOutline,
  SettingsOutline,
  HardwareChipOutline,
  LogOutOutline,
  ChevronBackOutline,
  SearchOutline,
  EllipsisHorizontalOutline,
} from "@vicons/ionicons5";
import { api } from "@/api/client";
import { useAuth } from "@/composables/useAuth";
import { useTheme } from "@/composables/useTheme";
import { useSiderCollapsed } from "@/composables/useSiderCollapsed";
import { provideBreadcrumbTail } from "@/composables/useBreadcrumbTail";
import { useBreakpoint } from "@/composables/useBreakpoint";
import { useConditions } from "@/composables/useConditions";
import type { CapabilitiesOut } from "@/types/api";
import { canAdmin } from "@/utils/roles";
import LogoMark from "@/components/LogoMark.vue";
import CommandPalette from "@/components/kit/CommandPalette.vue";
import ConditionBanner from "@/components/kit/ConditionBanner.vue";
import ProfileMark from "@/components/kit/ProfileMark.vue";

const route = useRoute();
const router = useRouter();
const { username, role, logout, clearSession } = useAuth();
const { isDark, setTheme, mode } = useTheme();
const { collapsed, setCollapsed, restoreDesktopPreference } = useSiderCollapsed();
const { isMobile } = useBreakpoint();
const capabilities = ref<CapabilitiesOut | null>(null);
const { items: conditions } = useConditions(capabilities);
const dismissed = ref<string[]>([]);
const paletteOpen = ref(false);
const moreOpen = ref(false);
const { tail: breadcrumbTail, override: breadcrumbOverride } = provideBreadcrumbTail();

function menuIcon(Icon: typeof PeopleOutline) {
  return () => h(NIcon, null, { default: () => h(Icon) });
}

const menuOptions = computed<MenuOption[]>(() => {
  const use: MenuOption[] = [
    { label: "Overview", key: "/", icon: menuIcon(HomeOutline) },
    { label: "Library", key: "/enrollments", icon: menuIcon(PeopleOutline) },
    { label: "Recognize", key: "/test", icon: menuIcon(ScanOutline) },
    { label: "Activity", key: "/logs", icon: menuIcon(PulseOutline) },
  ];
  const setup: MenuOption[] = [
    { label: "Connections", key: "/integrations", icon: menuIcon(LinkOutline) },
    { label: "Users", key: "/users", icon: menuIcon(PeopleCircleOutline) },
    { label: "API keys", key: "/keys", icon: menuIcon(KeyOutline) },
  ];
  if (canAdmin(role.value)) {
    setup.push({ label: "Models", key: "/models", icon: menuIcon(HardwareChipOutline) });
  }
  setup.push({ label: "Settings", key: "/settings", icon: menuIcon(SettingsOutline) });

  if (collapsed.value) return [...use, ...setup];
  return [
    { type: "group", label: "Use", key: "group-use", children: use },
    { type: "group", label: "Set up", key: "group-setup", children: setup },
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
  if (breadcrumbOverride.value && breadcrumbOverride.value.length >= 2) {
    const parent = breadcrumbOverride.value[breadcrumbOverride.value.length - 2];
    if (parent.to) return parent.to;
  }
  const crumbs = route.meta.breadcrumbs;
  if (!crumbs?.length || crumbs.length < 2) return null;
  return crumbs[0].to ?? null;
});

const visibleConditions = computed(() =>
  conditions.value.filter((c) => !dismissed.value.includes(c.id)),
);

const userOptions = computed(() => [
  { label: "Light", key: "theme-light" },
  { label: "Dark", key: "theme-dark" },
  { label: "System", key: "theme-system" },
  { type: "divider", key: "d1" },
  { label: "API docs", key: "docs" },
  { type: "divider", key: "d2" },
  {
    label: "Sign out",
    key: "logout",
    icon: () => h(NIcon, null, { default: () => h(LogOutOutline) }),
  },
]);

const mobileTabs = [
  { key: "/", label: "Overview", icon: HomeOutline },
  { key: "/enrollments", label: "Library", icon: PeopleOutline },
  { key: "/test", label: "Recognize", icon: ScanOutline },
  { key: "/logs", label: "Activity", icon: PulseOutline },
];

function onMenuSelect(key: string) {
  void router.push(key);
  moreOpen.value = false;
}

async function handleUserAction(key: string) {
  if (key === "logout") {
    await logout();
    void router.push("/login");
    return;
  }
  if (key === "docs") {
    window.open("/docs", "_blank", "noopener");
    return;
  }
  if (key.startsWith("theme-")) {
    setTheme(key.replace("theme-", "") as "light" | "dark" | "system");
  }
}

function onHotkey(e: KeyboardEvent) {
  const target = e.target as HTMLElement | null;
  const typing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
  if (typing) return;
  if (e.key === "n") void router.push("/enrollments/new");
  if (e.key === "r") void router.push("/test");
}

async function loadCapabilities() {
  try {
    capabilities.value = await api<CapabilitiesOut>("/v1/capabilities");
  } catch {
    clearSession();
    void router.push("/login");
  }
}

onMounted(() => {
  window.addEventListener("keydown", onHotkey);
  window.addEventListener("or-hardware-changed", loadCapabilities);
  if (isMobile.value) setCollapsed(true, false);
  void loadCapabilities();
});

onUnmounted(() => {
  window.removeEventListener("keydown", onHotkey);
  window.removeEventListener("or-hardware-changed", loadCapabilities);
});

function onBreakpoint() {
  if (isMobile.value) setCollapsed(true, false);
  else restoreDesktopPreference();
}

watch(isMobile, onBreakpoint, { immediate: true });
</script>

<template>
  <NLayout has-sider class="app-shell" :class="{ dark: isDark, 'is-mobile': isMobile }">
    <NLayoutSider
      v-if="!isMobile"
      collapse-mode="width"
      :collapsed-width="60"
      :width="248"
      :collapsed="collapsed"
      show-trigger
      class="app-sider"
      @update:collapsed="setCollapsed"
    >
      <div class="sider-inner">
        <div class="sider-brand" :class="{ collapsed }">
          <LogoMark :size="28" class="logo" />
          <span v-if="!collapsed" class="brand-name">OpenRecognition</span>
        </div>
        <NMenu
          class="sider-menu"
          :value="activeKey"
          :collapsed="collapsed"
          :collapsed-width="60"
          :options="menuOptions"
          @update:value="onMenuSelect"
        />
        <div class="sider-account" :class="{ collapsed }">
          <NDropdown :options="userOptions" trigger="click" @select="handleUserAction">
            <button type="button" class="account-btn" :aria-label="username ?? 'Account'">
              <ProfileMark :label="username ?? 'User'" size="sm" />
              <span v-if="!collapsed" class="account-meta">
                <span class="account-name">{{ username ?? "User" }}</span>
                <span class="account-role">{{ role }} · {{ mode }}</span>
              </span>
            </button>
          </NDropdown>
          <p v-if="capabilities && !collapsed" class="sider-status">
            {{ capabilities.hardware.label }} · v{{ capabilities.version }}
          </p>
          <NTooltip v-else-if="capabilities" trigger="hover">
            <template #trigger>
              <p class="sider-status sider-status--collapsed">{{ capabilities.hardware.label.slice(0, 1) }}</p>
            </template>
            {{ capabilities.hardware.label }} · v{{ capabilities.version }}
          </NTooltip>
        </div>
      </div>
    </NLayoutSider>

    <NDrawer v-model:show="moreOpen" :width="280" placement="bottom" class="more-drawer">
      <div class="more-sheet">
        <p class="or-caps">More</p>
        <NMenu :value="activeKey" :options="menuOptions" @update:value="onMenuSelect" />
        <NDropdown :options="userOptions" trigger="click" @select="handleUserAction">
          <button type="button" class="account-btn">
            <ProfileMark :label="username ?? 'User'" size="sm" />
            <span class="account-meta">
              <span class="account-name">{{ username ?? "User" }}</span>
              <span class="account-role">{{ role }}</span>
            </span>
          </button>
        </NDropdown>
      </div>
    </NDrawer>

    <NLayout class="app-main">
      <header v-if="showBreadcrumbs || !isMobile" class="app-topbar">
        <div class="topbar-left">
          <NButton
            v-if="headerBackTo"
            quaternary
            circle
            :aria-label="'Back'"
            @click="router.push(headerBackTo)"
          >
            <template #icon>
              <NIcon><ChevronBackOutline /></NIcon>
            </template>
          </NButton>
          <nav v-if="showBreadcrumbs" class="crumbs" aria-label="Breadcrumb">
            <template v-for="(crumb, i) in headerBreadcrumbs" :key="i">
              <span v-if="i > 0" class="crumbs__sep">/</span>
              <button
                v-if="crumb.to && i < headerBreadcrumbs.length - 1"
                type="button"
                class="crumbs__link"
                @click="router.push(crumb.to)"
              >
                {{ crumb.label }}
              </button>
              <span v-else class="crumbs__now">{{ crumb.label }}</span>
            </template>
          </nav>
        </div>
        <NButton
          v-if="!isMobile"
          quaternary
          size="small"
          aria-label="Search"
          @click="paletteOpen = true"
        >
          <template #icon>
            <NIcon><SearchOutline /></NIcon>
          </template>
          <span class="search-hint">Search</span>
          <kbd class="search-kbd">⌘K</kbd>
        </NButton>
      </header>

      <NLayoutContent
        class="app-page-bg"
        :class="{ 'app-page-bg--contained': route.name === 'logs' }"
      >
        <div class="content-container">
          <ConditionBanner :items="visibleConditions" @dismiss="dismissed.push($event)" />
          <div class="page-slot">
            <RouterView v-slot="{ Component }">
              <Transition name="or-fade" mode="out-in">
                <component :is="Component" />
              </Transition>
            </RouterView>
          </div>
        </div>
      </NLayoutContent>
    </NLayout>

    <nav v-if="isMobile" class="bottom-bar" aria-label="Primary">
      <button
        v-for="tab in mobileTabs"
        :key="tab.key"
        type="button"
        class="bottom-bar__item"
        :class="{ 'is-active': activeKey === tab.key }"
        @click="router.push(tab.key)"
      >
        <NIcon :size="20" :component="tab.icon" />
        <span>{{ tab.label }}</span>
      </button>
      <button
        type="button"
        class="bottom-bar__item"
        :class="{ 'is-active': moreOpen }"
        @click="moreOpen = true"
      >
        <NIcon :size="20"><EllipsisHorizontalOutline /></NIcon>
        <span>More</span>
      </button>
    </nav>

    <CommandPalette v-model:show="paletteOpen" />
  </NLayout>
</template>

<style scoped>
.app-shell {
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

.app-shell.is-mobile {
  padding-bottom: calc(var(--or-bottombar-h) + env(safe-area-inset-bottom));
}

.app-shell > :deep(.n-layout-scroll-container) {
  display: flex;
  flex-wrap: nowrap;
  height: 100%;
  min-height: 0;
}

.app-sider {
  flex-shrink: 0;
  border-right: 1px solid var(--or-line);
}

.app-sider :deep(.n-layout-sider-scroll-container) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sider-inner {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  height: 100%;
}

.sider-menu {
  flex: 1;
  min-height: 0;
  padding: 4px 8px;
}

.sider-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 16px 12px;
}

.sider-brand.collapsed {
  justify-content: center;
  padding: 20px 8px 12px;
}

.brand-name {
  font-weight: 600;
  letter-spacing: -0.02em;
  white-space: nowrap;
}

.sider-account {
  margin-top: auto;
  padding: 12px;
  border-top: 1px solid var(--or-line);
}

.sider-account.collapsed {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.account-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 6px;
  border: 0;
  border-radius: var(--or-radius-sm);
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
  text-align: left;
}

.account-btn:hover {
  background: var(--or-hover);
}

.account-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.account-name {
  font-weight: 600;
  font-size: var(--or-text-small);
}

.account-role {
  font-size: var(--or-text-micro);
  color: var(--or-text-3);
  text-transform: capitalize;
}

.sider-status {
  margin: 8px 6px 0;
  font-size: var(--or-text-micro);
  color: var(--or-text-3);
}

.sider-status--collapsed {
  text-transform: uppercase;
  font-weight: 600;
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

.app-topbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  height: var(--or-topbar-h);
  padding: 0 var(--or-page-x);
  border-bottom: 1px solid var(--or-line);
  background: var(--or-surface);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.crumbs {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: var(--or-text-small);
  color: var(--or-text-3);
}

.crumbs__link {
  appearance: none;
  border: 0;
  background: none;
  color: var(--or-text-3);
  font: inherit;
  cursor: pointer;
  padding: 0;
}

.crumbs__link:hover,
.crumbs__now {
  color: var(--or-text-1);
}

.crumbs__now {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.search-hint {
  margin-right: 8px;
}

.search-kbd {
  font-family: var(--or-font-sans);
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--or-surface-sunken);
  color: var(--or-text-3);
}

.app-page-bg {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.app-page-bg--contained {
  overflow: hidden;
}

.app-page-bg--contained :deep(.n-layout-scroll-container) {
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.app-page-bg--contained .content-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.app-page-bg--contained .page-slot {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.bottom-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  display: flex;
  height: calc(var(--or-bottombar-h) + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  background: var(--or-surface);
  border-top: 1px solid var(--or-line);
}

.bottom-bar__item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  border: 0;
  background: none;
  color: var(--or-text-3);
  font: inherit;
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
}

.bottom-bar__item.is-active {
  color: var(--or-accent);
}

.more-sheet {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 8px 8px 24px;
}

.logo {
  flex-shrink: 0;
}
</style>
