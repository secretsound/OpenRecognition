import { ref } from "vue";
import { api } from "@/api/client";
import type { LoginResponse } from "@/types/api";

const username = ref<string | null>(null);
const role = ref<string | null>(null);

export function useAuth() {
  const isLoggedIn = () => username.value !== null;

  async function login(user: string, password: string) {
    const res = await api<LoginResponse>("/v1/auth/login", {
      method: "POST",
      json: { username: user, password },
    });
    username.value = res.username;
    role.value = res.role;
    return res;
  }

  async function logout() {
    try {
      await api("/v1/auth/logout", { method: "POST" });
    } finally {
      username.value = null;
      role.value = null;
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
  }

  return {
    username,
    role,
    isLoggedIn,
    login,
    logout,
    setSession,
    clearSession,
  };
}
