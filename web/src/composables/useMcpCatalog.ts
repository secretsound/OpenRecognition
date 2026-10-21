import { computed, ref } from "vue";
import { api } from "@/api/client";
import type { McpIntegrationOut, McpToolOut } from "@/types/api";

const catalog = ref<McpIntegrationOut | null>(null);
let loadPromise: Promise<void> | null = null;

export function scopesAllowTool(selectedScopes: string[], toolScope: string): boolean {
  if (selectedScopes.includes("admin")) return true;
  return selectedScopes.includes(toolScope);
}

export function toolsForScopes(
  tools: McpToolOut[],
  selectedScopes: string[],
): McpToolOut[] {
  return tools.filter((t) => scopesAllowTool(selectedScopes, t.scope));
}

export function useMcpCatalog() {
  async function ensureCatalog() {
    if (catalog.value) return catalog.value;
    if (!loadPromise) {
      loadPromise = api<McpIntegrationOut>("/v1/integrations/mcp").then((data) => {
        catalog.value = data;
      });
    }
    await loadPromise;
    return catalog.value!;
  }

  function hostConfigWithKey(apiKey: string): string {
    if (!catalog.value) return "";
    return catalog.value.host_config_json.replace("<api-key>", apiKey);
  }

  const suggestedMcpScopes = computed(() => catalog.value?.suggested_scopes ?? ["read", "recognize"]);

  return {
    catalog,
    ensureCatalog,
    hostConfigWithKey,
    suggestedMcpScopes,
    toolsForScopes,
  };
}

/** Default scopes for MCP clients (read + recognize, no enroll unless needed). */
export const MCP_KEY_SCOPES = ["read", "recognize"] as const;

export const MCP_KEY_SCOPES_FULL = ["read", "recognize", "enroll"] as const;
