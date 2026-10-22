import { ref } from "vue";
import { api } from "@/api/client";
import type { AuthMeOut, EnrollmentGrantOut, GroupBriefOut, LoginResponse } from "@/types/api";
import { canWrite } from "@/utils/roles";

const username = ref<string | null>(null);
const role = ref<string | null>(null);
const groups = ref<GroupBriefOut[]>([]);
const enrollmentGrants = ref<EnrollmentGrantOut[]>([]);
const libraryLimited = ref(false);

function applyMe(me: AuthMeOut) {
  role.value = me.role ?? role.value;
  groups.value = me.groups ?? [];
  enrollmentGrants.value = me.enrollment_grants ?? [];
  libraryLimited.value = Boolean(me.library_limited);
}

export function useAuth() {
  const isLoggedIn = () => username.value !== null;

  async function login(user: string, password: string) {
    const res = await api<LoginResponse>("/v1/auth/login", {
      method: "POST",
      json: { username: user, password },
    });
    username.value = res.username;
    role.value = res.role;
    await refreshMe();
    return res;
  }

  async function refreshMe() {
    try {
      const me = await api<AuthMeOut>("/v1/auth/me", { skipAuthRedirect: true });
      applyMe(me);
      if (me.name && me.credential_type === "session") {
        username.value = me.name;
      }
    } catch {
      groups.value = [];
      enrollmentGrants.value = [];
      libraryLimited.value = false;
    }
  }

  async function logout() {
    try {
      await api("/v1/auth/logout", { method: "POST" });
    } finally {
      clearSession();
      sessionStorage.removeItem("or-user");
      sessionStorage.removeItem("or-role");
    }
  }

  function setSession(user: string, userRole: string) {
    username.value = user;
    role.value = userRole;
  }

  function clearSession() {
    username.value = null;
    role.value = null;
    groups.value = [];
    enrollmentGrants.value = [];
    libraryLimited.value = false;
  }

  function grantFor(enrollmentId: string | null | undefined) {
    if (!enrollmentId) return null;
    return enrollmentGrants.value.find((g) => g.enrollment_id === enrollmentId) ?? null;
  }

  function canAddSamples(enrollmentId: string | null | undefined) {
    if (canWrite(role.value)) return true;
    return Boolean(grantFor(enrollmentId)?.can_add_samples);
  }

  function canManageEnrollment(enrollmentId: string | null | undefined) {
    if (canWrite(role.value)) return true;
    return Boolean(grantFor(enrollmentId)?.can_manage);
  }

  return {
    username,
    role,
    groups,
    enrollmentGrants,
    libraryLimited,
    isLoggedIn,
    login,
    logout,
    setSession,
    clearSession,
    refreshMe,
    canAddSamples,
    canManageEnrollment,
  };
}
