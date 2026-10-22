import { computed, onMounted, ref } from "vue";
import { api } from "@/api/client";
import type { AppSettingsOut, CapabilitiesOut, WyomingIntegrationOut } from "@/types/api";
import { isSecureEnoughForMic } from "@/utils/secureContext";

export type ConditionTone = "warning" | "error" | "info";

export interface Condition {
  id: string;
  tone: ConditionTone;
  title: string;
  detail: string;
  to?: string;
}

const settings = ref<AppSettingsOut | null>(null);
const wyoming = ref<WyomingIntegrationOut | null>(null);
const loaded = ref(false);

export function useConditions(capabilities: { value: CapabilitiesOut | null }) {
  const insecure = computed(() => typeof window !== "undefined" && !isSecureEnoughForMic());

  const items = computed<Condition[]>(() => {
    const list: Condition[] = [];
    if (insecure.value) {
      list.push({
        id: "https",
        tone: "warning",
        title: "Microphone and camera need HTTPS",
        detail:
          "This page is not a secure context. Open the console over HTTPS, or use localhost, to record and capture.",
      });
    }
    if (settings.value?.maintenance_mode) {
      list.push({
        id: "maintenance",
        tone: "warning",
        title: "Maintenance mode is on",
        detail: "Recognition and new samples are paused. You can still use this console.",
        to: "/settings",
      });
    }
    const inference = capabilities.value?.inference;
    const models = capabilities.value?.models ?? {};
    const missingOnnx = inference?.effective_summary === "heuristic" && Object.keys(models).length === 0;
    if (missingOnnx) {
      list.push({
        id: "models",
        tone: "info",
        title: "Matching is using the built-in guess",
        detail: "Download a model set for real voice and face matching.",
        to: "/models",
      });
    }
    if (wyoming.value?.ports_conflict) {
      list.push({
        id: "wyoming-ports",
        tone: "error",
        title: "Wyoming listen and upstream share a port",
        detail: "Change one of the addresses so Home Assistant can connect.",
        to: "/integrations/wyoming",
      });
    } else if (wyoming.value?.listen_error) {
      list.push({
        id: "wyoming-listen",
        tone: "error",
        title: "Wyoming failed to listen",
        detail: wyoming.value.listen_error,
        to: "/integrations/wyoming",
      });
    }
    return list;
  });

  async function refresh() {
    try {
      const [s, w] = await Promise.all([
        api<AppSettingsOut>("/v1/admin/settings").catch(() => null),
        api<WyomingIntegrationOut>("/v1/integrations/wyoming").catch(() => null),
      ]);
      settings.value = s;
      wyoming.value = w;
    } finally {
      loaded.value = true;
    }
  }

  onMounted(() => {
    if (!loaded.value) void refresh();
  });

  return { items, refresh, settings, wyoming };
}
