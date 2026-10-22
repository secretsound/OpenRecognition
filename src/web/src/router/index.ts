import { createRouter, createWebHistory } from "vue-router";
import { api, ApiError, setUnauthorizedHandler } from "@/api/client";
import { useAuth } from "@/composables/useAuth";
import { safeAppPath } from "@/utils/safeRedirect";
import AppLayout from "@/layouts/AppLayout.vue";

const USER_KEY = "or-user";
const ROLE_KEY = "or-role";

import type { AppBreadcrumb } from "@/composables/useBreadcrumbTail";

declare module "vue-router" {
  interface RouteMeta {
    public?: boolean;
    /** Shown in the app header when there are two or more segments. */
    breadcrumbs?: AppBreadcrumb[];
    /** Header back button target; defaults to first breadcrumb `to` when depth ≥ 2. */
    backTo?: string;
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("@/views/LoginView.vue"),
      meta: { public: true },
    },
    {
      path: "/",
      component: AppLayout,
      children: [
        {
          path: "",
          name: "home",
          component: () => import("@/views/HomeView.vue"),
          meta: { breadcrumbs: [{ label: "Home" }] },
        },
        {
          path: "enrollments",
          name: "enrollments",
          component: () => import("@/views/EnrollmentsView.vue"),
          meta: { breadcrumbs: [{ label: "Library" }] },
        },
        {
          path: "enrollments/new",
          name: "enroll-new",
          component: () => import("@/views/EnrollView.vue"),
          meta: {
            breadcrumbs: [
              { label: "Library", to: "/enrollments" },
              { label: "New" },
            ],
          },
        },
        {
          path: "test",
          name: "test",
          component: () => import("@/views/TestView.vue"),
          meta: { breadcrumbs: [{ label: "Recognize" }] },
        },
        {
          path: "enrollments/:id",
          name: "enrollment-detail",
          component: () => import("@/views/EnrollmentDetailView.vue"),
          meta: {
            breadcrumbs: [
              { label: "Library", to: "/enrollments" },
              { label: "Detail" },
            ],
          },
        },
        {
          path: "enrollments/:id/settings",
          name: "enrollment-settings",
          redirect: (to) => ({
            name: "enrollment-detail",
            params: { id: to.params.id },
            query: { tab: "settings" },
          }),
        },
        {
          path: "enrollments/:id/training",
          name: "enrollment-training",
          redirect: (to) => ({
            name: "enrollment-detail",
            params: { id: to.params.id },
            query: { tab: "samples", teach: "1" },
          }),
        },
        {
          path: "users",
          name: "users",
          component: () => import("@/views/UsersView.vue"),
          meta: { breadcrumbs: [{ label: "Users" }] },
        },
        {
          path: "groups",
          name: "groups",
          component: () => import("@/views/GroupsView.vue"),
          meta: { breadcrumbs: [{ label: "Groups" }] },
        },
        {
          path: "groups/:id",
          name: "group-detail",
          component: () => import("@/views/GroupDetailView.vue"),
          meta: {
            breadcrumbs: [
              { label: "Groups", to: "/groups" },
              { label: "Detail" },
            ],
          },
        },
        {
          path: "keys",
          name: "keys",
          component: () => import("@/views/ApiKeysView.vue"),
          meta: { breadcrumbs: [{ label: "API keys" }] },
        },
        {
          path: "integrations/:tab?",
          name: "integrations",
          component: () => import("@/views/IntegrationsView.vue"),
          meta: { breadcrumbs: [{ label: "Connections" }] },
        },
        { path: "webhooks", redirect: { name: "integrations", params: { tab: "webhooks" } } },
        {
          path: "logs",
          name: "logs",
          component: () => import("@/views/LogsView.vue"),
          meta: { breadcrumbs: [{ label: "Activity" }] },
        },
        {
          path: "models",
          name: "models",
          component: () => import("@/views/ModelsView.vue"),
          meta: { breadcrumbs: [{ label: "Models" }] },
        },
        {
          path: "settings",
          name: "settings",
          component: () => import("@/views/SettingsView.vue"),
          meta: { breadcrumbs: [{ label: "Settings" }] },
        },
      ],
    },
  ],
});

function forgetSession() {
  const { clearSession } = useAuth();
  clearSession();
  sessionStorage.removeItem(USER_KEY);
  sessionStorage.removeItem(ROLE_KEY);
}

function loginTarget(redirect: string | null) {
  return redirect ? { name: "login" as const, query: { redirect } } : { name: "login" as const };
}

setUnauthorizedHandler(() => {
  forgetSession();
  const current = router.currentRoute.value;
  if (current.name === "login") return;
  const redirect = safeAppPath(current.fullPath);
  void router.push(loginTarget(redirect));
});

router.beforeEach(async (to) => {
  if (to.meta.public) return true;

  const { username, setSession, refreshMe } = useAuth();
  const storedUser = sessionStorage.getItem(USER_KEY);
  const storedRole = sessionStorage.getItem(ROLE_KEY);
  if (!username.value && storedUser && storedRole) {
    setSession(storedUser, storedRole);
  }

  try {
    await api("/v1/capabilities", { skipAuthRedirect: true });
    if (username.value || storedUser) {
      await refreshMe();
    }
    return true;
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 401) {
      if (username.value || (storedUser && storedRole)) return true;
    }
    forgetSession();
    return loginTarget(safeAppPath(to.fullPath));
  }
});

export default router;
