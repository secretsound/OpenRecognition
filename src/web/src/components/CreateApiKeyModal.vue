<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  NModal,
  NForm,
  NFormItem,
  NInput,
  NCheckbox,
  NButton,
  useMessage,
} from "naive-ui";
import type { FormInst } from "naive-ui";
import { api } from "@/api/client";
import { ApiError } from "@/api/client";
import type { ApiKeyCreated, McpIntegrationOut, McpToolOut } from "@/types/api";
import { scopesAllowTool } from "@/composables/useMcpCatalog";

type OpenPreset = "default" | "mcp" | "integration";

const show = defineModel<boolean>("show", { required: true });

const props = defineProps<{
  catalog: McpIntegrationOut | null;
  preset?: OpenPreset;
}>();

const emit = defineEmits<{
  created: [payload: ApiKeyCreated];
}>();

const message = useMessage();
const formRef = ref<FormInst | null>(null);
const creating = ref(false);

const form = ref({
  name: "",
  scopes: [] as string[],
  mcpTools: [] as string[],
});

type Purpose = "home-assistant" | "assistant" | "full" | "custom";

const step = ref<1 | 2>(1);
const purpose = ref<Purpose | null>(null);
const showDetails = ref(false);

const scopeItems = [
  { id: "read", label: "View", hint: "See the library, who was recognized, and whether the server is ready." },
  { id: "recognize", label: "Recognize", hint: "Match a voice, photo, or video." },
  { id: "enroll", label: "Add to the library", hint: "Create enrollments and add samples." },
  { id: "admin", label: "Full access", hint: "Everything the web API can do, including users and settings." },
] as const;

const toolLabels: Record<string, string> = {
  get_health: "Server status",
  get_capabilities: "What this server can do",
  list_enrollments: "Library",
  get_presence: "Who was seen recently",
  audio_gate: "Check if a clip is speech",
  recognize_audio: "Match a voice",
  recognize_image: "Match a photo",
  recognize_image_url: "Match a photo from a link",
  enroll_from_paths: "Add someone from files on this server",
};

const modalTitle = computed(() =>
  step.value === 1 ? "What is this key for?" : "Name and permissions",
);

const showEditor = computed(() => purpose.value === "custom" || showDetails.value);

const summaryLines = computed(() => {
  const lines: string[] = [];
  if (form.value.scopes.includes("admin")) {
    lines.push("Full access to the web API.");
  } else {
    if (form.value.scopes.includes("read")) lines.push("View the library and server status.");
    if (form.value.scopes.includes("recognize")) lines.push("Match voices, photos, and video.");
    if (form.value.scopes.includes("enroll")) lines.push("Add and change the library.");
  }
  if (!form.value.scopes.length) lines.push("No web API access.");
  if (form.value.mcpTools.length) {
    const n = form.value.mcpTools.length;
    lines.push(`${n} assistant tool${n === 1 ? "" : "s"}.`);
  } else {
    lines.push("No assistant tools.");
  }
  return lines;
});

const allMcpTools = computed((): McpToolOut[] => props.catalog?.tools ?? []);

const toolGroups = computed(() => {
  if (!props.catalog) return [];
  const groups: Record<string, McpToolOut[]> = {};
  for (const t of allMcpTools.value) {
    (groups[t.scope] ??= []).push(t);
  }
  const order = ["read", "recognize", "enroll"];
  return order
    .filter((s) => groups[s]?.length)
    .map((scope) => ({
      scope,
      tools: groups[scope]!,
    }));
});

function resetForm(preset: OpenPreset = "default") {
  showDetails.value = false;
  if (preset === "integration") {
    purpose.value = "home-assistant";
    step.value = 2;
    form.value = { name: "home-assistant", scopes: ["recognize"], mcpTools: [] };
  } else if (preset === "mcp") {
    purpose.value = "assistant";
    step.value = 2;
    form.value = { name: "mcp-client", scopes: [], mcpTools: assistantToolNames() };
  } else {
    purpose.value = null;
    step.value = 1;
    form.value = { name: "", scopes: [], mcpTools: [] };
  }
}

function choosePurpose(kind: Purpose) {
  purpose.value = kind;
  showDetails.value = kind === "custom";
  if (kind === "home-assistant") applyQuickStart("home-assistant");
  else if (kind === "assistant") applyQuickStart("mcp-assistant");
  else if (kind === "full") applyQuickStart("full-api");
  else form.value = { name: "", scopes: [], mcpTools: [] };
}

function setScope(id: string, on: boolean) {
  const next = new Set(form.value.scopes);
  if (on) next.add(id);
  else next.delete(id);
  form.value.scopes = [...next];
}

function toggleScope(id: string) {
  setScope(id, !form.value.scopes.includes(id));
}

function setTool(name: string, on: boolean) {
  const next = new Set(form.value.mcpTools);
  if (on) next.add(name);
  else next.delete(name);
  form.value.mcpTools = [...next];
}

function toggleTool(name: string) {
  setTool(name, !form.value.mcpTools.includes(name));
}

function toolLabel(name: string) {
  return toolLabels[name] ?? name.replaceAll("_", " ");
}

function groupTitle(scope: string) {
  if (scope === "read") return "View";
  if (scope === "recognize") return "Recognize";
  if (scope === "enroll") return "Add to the library";
  return scope;
}

function assistantToolNames(): string[] {
  if (!props.catalog) return [];
  return props.catalog.tools
    .filter((t) => t.scope === "read" || t.scope === "recognize")
    .map((t) => t.name);
}

function allToolNames(): string[] {
  return props.catalog?.tools.map((t) => t.name) ?? [];
}

function applyQuickStart(kind: "home-assistant" | "mcp-assistant" | "full-api") {
  if (kind === "home-assistant") {
    form.value = { name: "home-assistant", scopes: ["recognize"], mcpTools: [] };
  } else if (kind === "mcp-assistant") {
    form.value = { name: "mcp-client", scopes: [], mcpTools: assistantToolNames() };
  } else {
    form.value = { name: "admin", scopes: ["admin"], mcpTools: allToolNames() };
  }
}

function selectGroup(scope: string, selected: boolean) {
  const group = toolGroups.value.find((g) => g.scope === scope);
  if (!group) return;
  const set = new Set(form.value.mcpTools);
  for (const t of group.tools) {
    if (selected) set.add(t.name);
    else set.delete(t.name);
  }
  form.value.mcpTools = [...set];
}

function isGroupFullySelected(scope: string): boolean {
  const group = toolGroups.value.find((g) => g.scope === scope);
  if (!group) return false;
  return group.tools.every((t) => form.value.mcpTools.includes(t.name));
}

function sameStringList(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((v, i) => v === b[i]);
}

function close() {
  show.value = false;
}

async function submit() {
  await formRef.value?.validate();
  if (!form.value.scopes.length && !form.value.mcpTools.length) {
    message.warning("Choose at least one permission.");
    return;
  }
  creating.value = true;
  try {
    const res = await api<ApiKeyCreated>("/v1/auth/keys", {
      method: "POST",
      json: {
        name: form.value.name,
        scopes: form.value.scopes,
        mcp_tools: form.value.mcpTools,
      },
    });
    emit("created", res);
    close();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to create key");
  } finally {
    creating.value = false;
  }
}

/** Keep MCP tools in sync when REST scopes shrink (only while modal is open). */
watch(
  () => form.value.scopes,
  () => {
    if (!show.value || !props.catalog) return;
    const allowed = new Set(
      form.value.scopes.length === 0
        ? allMcpTools.value.map((t) => t.name)
        : allMcpTools.value
            .filter((t) => scopesAllowTool(form.value.scopes, t.scope))
            .map((t) => t.name),
    );
    const next = form.value.mcpTools.filter((n) => allowed.has(n));
    if (!sameStringList(next, form.value.mcpTools)) {
      form.value.mcpTools = next;
    }
  },
  { deep: true },
);

/** Selecting MCP tools adds the REST scopes they require. */
watch(
  () => form.value.mcpTools,
  (tools) => {
    if (!show.value || !props.catalog) return;
    const scopes = new Set(form.value.scopes);
    for (const name of tools) {
      const tool = props.catalog.tools.find((t) => t.name === name);
      if (tool) scopes.add(tool.scope);
    }
    const next = [...scopes].sort();
    const current = [...form.value.scopes].sort();
    if (!sameStringList(next, current)) {
      form.value.scopes = [...scopes];
    }
  },
  { deep: true },
);

watch(show, (open) => {
  if (open) resetForm(props.preset ?? "default");
});
</script>

<template>
  <NModal
    v-model:show="show"
    preset="card"
    :title="modalTitle"
    class="create-key-modal or-modal"
    :mask-closable="!creating"
  >
    <p class="step-kicker">Step {{ step }} of 2</p>
    <p v-if="step === 1" class="modal-lead">
      Start from what this key will be used for. You can change the details on the next step.
    </p>
    <p v-else class="modal-lead">
      Give the key a name, then keep the suggested permissions or change them.
    </p>

    <div v-if="step === 1" class="purpose-grid">
      <button
        type="button"
        class="purpose-card"
        :class="{ 'is-selected': purpose === 'home-assistant' }"
        @click="choosePurpose('home-assistant')"
      >
        <span class="purpose-card__title">Home Assistant</span>
        <span class="purpose-card__desc">
          Recognize people from automations. This key cannot change the library.
        </span>
      </button>
      <button
        type="button"
        class="purpose-card"
        :class="{ 'is-selected': purpose === 'assistant' }"
        @click="choosePurpose('assistant')"
      >
        <span class="purpose-card__title">AI assistant</span>
        <span class="purpose-card__desc">
          Let Claude or Cursor look up the library and try a match.
        </span>
      </button>
      <button
        type="button"
        class="purpose-card"
        :class="{ 'is-selected': purpose === 'full' }"
        @click="choosePurpose('full')"
      >
        <span class="purpose-card__title">Full access</span>
        <span class="purpose-card__desc">
          Everything, including adding people and changing settings.
        </span>
      </button>
      <button
        type="button"
        class="purpose-card"
        :class="{ 'is-selected': purpose === 'custom' }"
        @click="choosePurpose('custom')"
      >
        <span class="purpose-card__title">Custom</span>
        <span class="purpose-card__desc">
          Choose each permission yourself.
        </span>
      </button>
    </div>

    <NForm v-else ref="formRef" :model="form" label-placement="top" class="create-key-form">
      <NFormItem
        label="Name"
        path="name"
        :rule="{ required: true, message: 'Name is required' }"
      >
        <NInput v-model:value="form.name" placeholder="For example, kitchen-camera" />
      </NFormItem>

      <section v-if="!showEditor" class="perm-summary">
        <h3 class="perm-heading">This key can</h3>
        <ul>
          <li v-for="line in summaryLines" :key="line">{{ line }}</li>
        </ul>
        <NButton text type="primary" @click="showDetails = true">Change permissions</NButton>
      </section>

      <template v-else>
        <section class="perm-block">
          <h3 class="perm-heading">Web API</h3>
          <p class="perm-intro">What other apps can do over HTTP, including Home Assistant.</p>
          <div
            v-for="item in scopeItems"
            :key="item.id"
            class="perm-row"
            @click="toggleScope(item.id)"
          >
            <span class="perm-row__copy">
              <span class="perm-row__label">{{ item.label }}</span>
              <span class="perm-row__hint">{{ item.hint }}</span>
            </span>
            <NCheckbox
              :checked="form.scopes.includes(item.id)"
              @update:checked="(on: boolean) => setScope(item.id, on)"
              @click.stop
            />
          </div>
        </section>

        <section class="perm-block">
          <h3 class="perm-heading">Assistant tools</h3>
          <p class="perm-intro">What Claude, Cursor, and similar assistants can call.</p>
          <p v-if="!catalog" class="perm-intro">Loading tools…</p>
          <div v-for="group in toolGroups" :key="group.scope" class="tool-group">
            <div class="tool-group__head">
              <h4>{{ groupTitle(group.scope) }}</h4>
              <NButton
                text
                type="primary"
                @click="selectGroup(group.scope, !isGroupFullySelected(group.scope))"
              >
                {{ isGroupFullySelected(group.scope) ? "Clear" : "Select all" }}
              </NButton>
            </div>
            <div
              v-for="tool in group.tools"
              :key="tool.name"
              class="perm-row"
              @click="toggleTool(tool.name)"
            >
              <span class="perm-row__copy">
                <span class="perm-row__label">{{ toolLabel(tool.name) }}</span>
                <span class="perm-row__hint">{{ tool.description }}</span>
              </span>
              <NCheckbox
                :checked="form.mcpTools.includes(tool.name)"
                @update:checked="(on: boolean) => setTool(tool.name, on)"
                @click.stop
              />
            </div>
          </div>
        </section>
      </template>
    </NForm>

    <template #footer>
      <div class="or-modal-footer">
        <NButton
          v-if="step === 2"
          quaternary
          class="footer-back"
          :disabled="creating"
          @click="step = 1"
        >
          Back
        </NButton>
        <NButton :disabled="creating" @click="close">Cancel</NButton>
        <NButton
          v-if="step === 1"
          type="primary"
          :disabled="!purpose"
          @click="step = 2"
        >
          Continue
        </NButton>
        <NButton v-else type="primary" :loading="creating" @click="submit">Create key</NButton>
      </div>
    </template>
  </NModal>
</template>

<style scoped>
.step-kicker {
  margin: 0 0 6px;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--n-text-color-3);
}

.modal-lead {
  margin: 0 0 20px;
  max-width: 40rem;
  font-size: 0.9375rem;
  line-height: 1.5;
  color: var(--n-text-color-2);
}

.purpose-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.purpose-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  width: 100%;
  padding: 16px 18px;
  border-radius: var(--or-radius);
  border: 1px solid var(--n-border-color);
  background: transparent;
  color: var(--n-text-color);
  text-align: left;
  cursor: pointer;
  font: inherit;
}

.purpose-card:hover,
.purpose-card.is-selected {
  border-color: var(--n-primary-color);
}

.purpose-card.is-selected {
  box-shadow: inset 0 0 0 1px var(--n-primary-color);
}

.purpose-card__title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--n-text-color);
}

.purpose-card__desc {
  font-size: 0.875rem;
  line-height: 1.45;
  color: var(--n-text-color-3);
}

.create-key-form :deep(.n-form-item) {
  margin-bottom: 20px;
}

.perm-summary,
.perm-block {
  margin-top: 4px;
}

.perm-summary ul {
  margin: 8px 0 12px;
  padding-left: 1.15rem;
  color: var(--n-text-color-2);
  line-height: 1.55;
}

.perm-heading {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.perm-intro {
  margin: 6px 0 4px;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--n-text-color-3);
}

.perm-block + .perm-block {
  margin-top: 28px;
}

.perm-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 16px 0;
  border-top: 1px solid var(--or-line, var(--n-border-color));
  cursor: pointer;
}

.perm-row__copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.perm-row__label {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.perm-row__hint {
  font-size: 0.875rem;
  line-height: 1.45;
  color: var(--n-text-color-3);
}

.tool-group {
  margin-top: 8px;
}

.tool-group__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 18px;
}

.tool-group__head h4 {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
}

.footer-back {
  margin-right: auto;
}

@media (max-width: 640px) {
  .purpose-grid {
    grid-template-columns: 1fr;
  }

  .perm-row {
    gap: 12px;
  }
}
</style>

<style>
.create-key-modal .n-card-content {
  max-height: min(62vh, 560px);
  overflow: auto;
}
</style>
