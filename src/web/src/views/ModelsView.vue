<script setup lang="ts">
import { computed, h, onMounted, ref, watch, type VNode } from "vue";
import { useRouter } from "vue-router";
import {
  NButton,
  NTag,
  NAlert,
  NSkeleton,
  NPopconfirm,
  NIcon,
  NSelect,
  NInput,
  NDataTable,
  NCollapse,
  NCollapseItem,
  NDropdown,
  NModal,
  NForm,
  NFormItem,
  NInputNumber,
  useDialog,
  useMessage,
} from "naive-ui";
import type { DataTableColumns, SelectOption } from "naive-ui";
import { CloudDownloadOutline, TrashOutline } from "@vicons/ionicons5";
import { api } from "@/api/client";
import type {
  InferenceBackend,
  ModelCatalogEntry,
  ModelDownloadResponse,
  ModelsStatusOut,
} from "@/types/api";
import AppPageHeader from "@/components/AppPageHeader.vue";
import { ApiError } from "@/api/client";
import { useAuth } from "@/composables/useAuth";

const message = useMessage();
const dialog = useDialog();
const router = useRouter();
const { role } = useAuth();

const loading = ref(true);
const downloading = ref(false);
const downloadingKey = ref<string | null>(null);
const deletingKey = ref<string | null>(null);
const reloading = ref(false);
const status = ref<ModelsStatusOut | null>(null);
const inferenceDraft = ref<InferenceBackend>("auto");
const savingInference = ref(false);
const advancedOpen = ref<string[]>([]);
const search = ref("");
const recommendationFilter = ref<string | null>(null);
const groupFilter = ref<string | null>(null);
const statusFilter = ref<string | null>(null);
const showModelForm = ref(false);
const editingKey = ref<string | null>(null);
const savingModel = ref(false);
const usingKey = ref<string | null>(null);
const formLabel = ref("");
const formCategory = ref("voice_match");
const formVersion = ref("");
const formUrl = ref("");
const formOnnx = ref<Record<string, string | number>>({});

const settingLabels: Record<string, string> = {
  embed_dim: "Embedding size",
  input_size: "Input size",
  conf_thres: "Minimum score",
  input_norm: "Color scaling",
  preprocessor: "Audio preparation",
  sample_rate: "Sample rate",
  num_mel_bins: "Mel bands",
  max_seconds: "Max length (seconds)",
  backend: "File type",
};

const REC_KEY = "or-model-recommendation";

const inferenceOptions: SelectOption[] = [
  { label: "Automatic", value: "auto" },
  { label: "Downloaded files", value: "onnx" },
  { label: "Built-in guess", value: "heuristic" },
];

const statusOptions: SelectOption[] = [
  { label: "Ready", value: "ready" },
  { label: "Not downloaded", value: "missing" },
];

function readRecommendation(): string | null {
  try {
    return localStorage.getItem(REC_KEY);
  } catch {
    return null;
  }
}

recommendationFilter.value = readRecommendation();

watch(recommendationFilter, (value) => {
  try {
    if (value) localStorage.setItem(REC_KEY, value);
    else localStorage.removeItem(REC_KEY);
  } catch {
    /* the filter still works for this visit */
  }
});

const missingCount = computed(
  () => status.value?.catalog.filter((m) => !m.on_disk).length ?? 0,
);

const catalogByKey = computed(() => {
  const map = new Map<string, ModelCatalogEntry>();
  for (const row of status.value?.catalog ?? []) {
    map.set(row.key, row);
  }
  return map;
});

const recommendations = computed(() => status.value?.recommendations ?? []);

const recommendationOptions = computed<SelectOption[]>(() =>
  recommendations.value.map((rec) => ({ label: rec.label, value: rec.id })),
);

const groupOptions = computed<SelectOption[]>(() =>
  [...(status.value?.categories ?? [])]
    .sort((a, b) => a.sort_order - b.sort_order)
    .map((cat) => ({ label: cat.label, value: cat.id })),
);

const selectedRecommendation = computed(
  () => recommendations.value.find((rec) => rec.id === recommendationFilter.value) ?? null,
);

function modelTitle(row: ModelCatalogEntry): string {
  return row.label || row.use_for;
}

function categoryLabel(id: string): string {
  return status.value?.categories.find((cat) => cat.id === id)?.label || id;
}

function categoryOrder(id: string): number {
  return status.value?.categories.find((cat) => cat.id === id)?.sort_order ?? 0;
}

function recommendationText(row: ModelCatalogEntry): string {
  const matched = recommendations.value.filter((rec) => rec.keys.includes(row.key));
  if (!matched.length) return "—";
  if (recommendations.value.length > 0 && matched.length === recommendations.value.length) {
    return "Every set";
  }
  return matched.map((rec) => rec.label).join(", ");
}

function missingDeps(row: ModelCatalogEntry): string[] {
  return row.depends_on.filter((dep) => !catalogByKey.value.get(dep)?.on_disk);
}

const filteredRows = computed(() => {
  let list = status.value?.catalog ?? [];
  const query = search.value.trim().toLowerCase();
  if (query) {
    list = list.filter((row) =>
      [modelTitle(row), row.version || "", row.use_for, categoryLabel(row.category), recommendationText(row)]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }
  if (selectedRecommendation.value) {
    const keys = new Set(selectedRecommendation.value.keys);
    list = list.filter((row) => keys.has(row.key));
  }
  if (groupFilter.value) list = list.filter((row) => row.category === groupFilter.value);
  if (statusFilter.value === "ready") list = list.filter((row) => row.on_disk);
  if (statusFilter.value === "missing") list = list.filter((row) => !row.on_disk);
  return [...list].sort(
    (a, b) =>
      categoryOrder(a.category) - categoryOrder(b.category) ||
      a.sort_order - b.sort_order ||
      modelTitle(a).localeCompare(modelTitle(b)),
  );
});

const filtersActive = computed(
  () =>
    search.value.trim().length > 0 ||
    recommendationFilter.value != null ||
    groupFilter.value != null ||
    statusFilter.value != null,
);

function clearFilters() {
  search.value = "";
  recommendationFilter.value = null;
  groupFilter.value = null;
  statusFilter.value = null;
}

const effectiveRuntime = computed(() => {
  const inf = status.value?.inference;
  if (!inf) return null;
  const isOnnx = inf.effective_summary === "onnx";
  return {
    summary: isOnnx ? "Downloaded files" : "Built-in guess",
    onnxCount: Object.values(inf.models).filter((v) => v === "onnx").length,
    heuristicCount: Object.values(inf.models).filter((v) => v === "heuristic").length,
    warnings: inf.warnings,
  };
});

const showGuessWarning = computed(() => {
  if (!status.value || !effectiveRuntime.value) return false;
  return effectiveRuntime.value.summary === "Built-in guess" && status.value.catalog.some((m) => m.on_disk);
});

const inferenceDirty = computed(
  () => status.value != null && inferenceDraft.value !== status.value.inference_backend,
);

function formatBytes(n: number | null | undefined): string {
  if (n == null || n <= 0) return "";
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function statusText(row: ModelCatalogEntry): string {
  if (!row.on_disk) return "Not downloaded";
  const size = formatBytes(row.size_bytes);
  return size ? `Ready · ${size}` : "Ready";
}

async function load() {
  loading.value = true;
  try {
    status.value = await api<ModelsStatusOut>("/v1/admin/models");
    inferenceDraft.value = status.value.inference_backend;
    const ids = new Set((status.value.recommendations ?? []).map((rec) => rec.id));
    if (recommendationFilter.value && !ids.has(recommendationFilter.value)) {
      recommendationFilter.value = null;
    }
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to load models");
  } finally {
    loading.value = false;
  }
}

async function download(keys?: string[], force = false) {
  downloading.value = true;
  try {
    const res = await api<ModelDownloadResponse>("/v1/admin/models/download", {
      method: "POST",
      json: { keys: keys ?? null, force },
    });
    for (const r of res.results) {
      if (r.status === "downloaded") {
        message.success(`${r.key}: ${r.message}`);
      } else if (r.status === "skipped") {
        message.info(`${r.key}: ${r.message}`);
      }
    }
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Download failed");
  } finally {
    downloading.value = false;
    downloadingKey.value = null;
  }
}

async function downloadOne(key: string, force = false) {
  downloadingKey.value = key;
  await download([key], force);
}

async function deleteOne(key: string) {
  deletingKey.value = key;
  try {
    const r = await api<{ key: string; status: string; message: string }>(
      `/v1/admin/models/${encodeURIComponent(key)}`,
      { method: "DELETE" },
    );
    message.success(r.message);
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Delete failed");
  } finally {
    deletingKey.value = null;
  }
}

async function reloadRuntime() {
  reloading.value = true;
  try {
    await api("/v1/admin/reload", { method: "POST" });
    message.success("Model runtime reloaded");
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Reload failed");
  } finally {
    reloading.value = false;
  }
}

async function saveInference() {
  savingInference.value = true;
  try {
    await api("/v1/admin/settings", {
      method: "PATCH",
      json: { inference_backend: inferenceDraft.value },
    });
    message.success("Saved");
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Failed to save");
  } finally {
    savingInference.value = false;
  }
}

function openAdvanced() {
  advancedOpen.value = ["advanced"];
}

function isCustom(row: ModelCatalogEntry): boolean {
  return row.origin === "custom";
}

function templateOnnx(category: string): Record<string, string | number> {
  const builtin = status.value?.catalog.find(
    (row) => row.category === category && row.origin !== "custom",
  );
  const onnx = builtin?.onnx ?? {};
  const copy: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(onnx)) {
    if (typeof value === "number" || typeof value === "string") copy[key] = value;
  }
  return copy;
}

function settingEntries(): { key: string; label: string; numeric: boolean }[] {
  return Object.keys(formOnnx.value).map((key) => ({
    key,
    label: settingLabels[key] || key,
    numeric: typeof formOnnx.value[key] === "number",
  }));
}

function openAddModel() {
  editingKey.value = null;
  formLabel.value = "";
  formCategory.value = status.value?.categories[0]?.id || "voice_match";
  formVersion.value = "";
  formUrl.value = "";
  formOnnx.value = templateOnnx(formCategory.value);
  showModelForm.value = true;
}

function onFormCategory(category: string) {
  formCategory.value = category;
  if (!editingKey.value) formOnnx.value = templateOnnx(category);
}

function openEditModel(row: ModelCatalogEntry) {
  editingKey.value = row.key;
  formLabel.value = modelTitle(row);
  formCategory.value = row.category;
  formVersion.value = row.version || "";
  formUrl.value = row.url;
  formOnnx.value = templateOnnx(row.category);
  for (const [key, value] of Object.entries(row.onnx ?? {})) {
    if (typeof value === "number" || typeof value === "string") formOnnx.value[key] = value;
  }
  showModelForm.value = true;
}

async function saveModel() {
  savingModel.value = true;
  try {
    const payload = {
      label: formLabel.value.trim(),
      version: formVersion.value.trim(),
      url: formUrl.value.trim(),
      onnx: formOnnx.value,
    };
    if (editingKey.value) {
      await api(`/v1/admin/models/custom/${encodeURIComponent(editingKey.value)}`, {
        method: "PATCH",
        json: payload,
      });
      message.success("Model updated. Re-download it if the file should change.");
    } else {
      await api("/v1/admin/models/custom", {
        method: "POST",
        json: { ...payload, category: formCategory.value },
      });
      message.success("Model added. Download it when you are ready.");
    }
    showModelForm.value = false;
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not save the model");
  } finally {
    savingModel.value = false;
  }
}

async function useModel(row: ModelCatalogEntry) {
  usingKey.value = row.key;
  try {
    await api("/v1/admin/models/active", {
      method: "POST",
      json: { category: row.category, key: row.key },
    });
    message.success(
      row.on_disk
        ? `${modelTitle(row)} is now in use`
        : `${modelTitle(row)} is selected. Download it before matching can use the file.`,
    );
    await load();
  } catch (e) {
    message.error(e instanceof ApiError ? e.message : "Could not switch models");
  } finally {
    usingKey.value = null;
  }
}

function confirmDeleteModel(row: ModelCatalogEntry) {
  dialog.warning({
    title: "Delete model",
    content: `Delete ${modelTitle(row)} from the list? The downloaded file is removed too.`,
    positiveText: "Delete",
    negativeText: "Cancel",
    onPositiveClick: async () => {
      try {
        await api(`/v1/admin/models/custom/${encodeURIComponent(row.key)}`, { method: "DELETE" });
        message.success("Model deleted");
        await load();
      } catch (e) {
        message.error(e instanceof ApiError ? e.message : "Could not delete the model");
      }
    },
  });
}

const columns = computed<DataTableColumns<ModelCatalogEntry>>(() => [
  {
    title: "Model",
    key: "label",
    minWidth: 160,
    sorter: (a, b) => modelTitle(a).localeCompare(modelTitle(b)),
    render(row) {
      return h("div", { class: "name-line" }, [
        h("strong", modelTitle(row)),
        row.active
          ? h(NTag, { size: "small", round: true, bordered: false, type: "success" }, { default: () => "In use" })
          : null,
        row.tier === "optional" && !isCustom(row)
          ? h(NTag, { size: "small", round: true, bordered: false }, { default: () => "Optional" })
          : null,
      ]);
    },
  },
  {
    title: "Category",
    key: "category",
    minWidth: 160,
    sorter: (a, b) => categoryLabel(a.category).localeCompare(categoryLabel(b.category)),
    render(row) {
      return categoryLabel(row.category);
    },
  },
  {
    title: "Version",
    key: "version",
    width: 170,
    ellipsis: { tooltip: true },
    sorter: (a, b) => (a.version || "").localeCompare(b.version || ""),
    render(row) {
      return row.version || "—";
    },
  },
  {
    title: "Used for",
    key: "use_for",
    minWidth: 220,
    render(row) {
      const deps = missingDeps(row);
      return h("div", [
        h("div", row.use_for),
        row.hardware_note ? h("div", { class: "cell-meta" }, row.hardware_note) : null,
        deps.length
          ? h(
              "div",
              { class: "cell-warn" },
              `Also download ${deps.map((key) => catalogByKey.value.get(key)?.label || key).join(", ")}.`,
            )
          : null,
      ]);
    },
  },
  {
    title: "Recommended for",
    key: "recommendations",
    minWidth: 140,
    render(row) {
      return recommendationText(row);
    },
  },
  {
    title: "Status",
    key: "on_disk",
    width: 150,
    render(row) {
      return h("span", { class: row.on_disk ? "is-ready" : "cell-meta" }, statusText(row));
    },
  },
  {
    title: "",
    key: "actions",
    width: 300,
    render(row) {
      const actions: VNode[] = [];
      if (!row.active) {
        actions.push(
          h(
            NButton,
            {
              size: "small",
              loading: usingKey.value === row.key,
              onClick: () => useModel(row),
            },
            { default: () => "Use" },
          ),
        );
      }
      actions.push(
        h(
          NButton,
          {
            size: "small",
            loading: downloadingKey.value === row.key,
            onClick: () => downloadOne(row.key, row.on_disk),
          },
          { default: () => (row.on_disk ? "Re-download" : "Download") },
        ),
      );
      if (isCustom(row)) {
        actions.push(
          h(
            NDropdown,
            {
              options: [
                { label: "Edit", key: "edit" },
                { label: "Delete", key: "delete" },
              ],
              onSelect: (key: string) => {
                if (key === "edit") openEditModel(row);
                else confirmDeleteModel(row);
              },
            },
            { default: () => h(NButton, { size: "small", quaternary: true }, { default: () => "More" }) },
          ),
        );
      }
      if (row.on_disk) {
        actions.push(
          h(
            NPopconfirm,
            { onPositiveClick: () => deleteOne(row.key) },
            {
              trigger: () =>
                h(
                  NButton,
                  { size: "small", quaternary: true, loading: deletingKey.value === row.key },
                  {
                    icon: () => h(NIcon, null, { default: () => h(TrashOutline) }),
                    default: () => "Remove",
                  },
                ),
              default: () => `Remove ${modelTitle(row)} from this server?`,
            },
          ),
        );
      }
      return h("div", { class: "row-actions" }, actions);
    },
  },
]);

onMounted(() => {
  if (role.value !== "admin") {
    router.replace("/enrollments");
    return;
  }
  void load();
});
</script>

<template>
  <div class="models-page">
    <AppPageHeader
      title="Models"
      description="Download what this server uses to recognize voices, faces, and pets."
    >
      <template #action>
        <NButton @click="openAddModel">Add a model</NButton>
        <NDropdown :options="[{ label: 'Reload models', key: 'reload' }]" @select="reloadRuntime">
          <NButton :loading="reloading">More</NButton>
        </NDropdown>
        <NButton
          v-if="missingCount > 0"
          type="primary"
          :loading="downloading && !downloadingKey"
          @click="download()"
        >
          <template #icon>
            <NIcon><CloudDownloadOutline /></NIcon>
          </template>
          Download missing ({{ missingCount }})
        </NButton>
      </template>
    </AppPageHeader>

    <NSkeleton v-if="loading && !status" text :repeat="6" />

    <template v-else-if="status">
      <NAlert v-if="showGuessWarning" type="warning" :bordered="false">
        <div class="guess-row">
          <span>Downloaded files are on this server, but matching is using the built-in guess.</span>
          <NButton text @click="openAdvanced">Change</NButton>
        </div>
      </NAlert>

      <div class="toolbar">
        <NInput
          v-model:value="search"
          class="search-control"
          clearable
          placeholder="Search models"
        />
        <NSelect
          v-model:value="recommendationFilter"
          class="filter-control"
          :options="recommendationOptions"
          clearable
          placeholder="Recommended set"
        />
        <NSelect
          v-model:value="groupFilter"
          class="filter-control"
          :options="groupOptions"
          clearable
          placeholder="Category"
        />
        <NSelect
          v-model:value="statusFilter"
          class="filter-control"
          :options="statusOptions"
          clearable
          placeholder="Status"
        />
      </div>
      <p v-if="selectedRecommendation?.description" class="hint">
        {{ selectedRecommendation.description }}
      </p>

      <p v-if="filteredRows.length === 0" class="filter-empty">
        Nothing matches.
        <NButton v-if="filtersActive" text type="primary" size="small" @click="clearFilters">
          Clear filters
        </NButton>
      </p>

      <template v-else>
        <div class="or-list-cards">
          <article v-for="row in filteredRows" :key="row.key" class="or-list-card model-card">
            <div class="model-card-copy">
              <span class="or-list-card__title">
                {{ modelTitle(row) }}
                <NTag v-if="row.active" size="small" round :bordered="false" type="success">In use</NTag>
              </span>
              <span class="or-list-card__meta">
                <span>{{ categoryLabel(row.category) }}</span>
                <span>{{ row.version || "—" }}</span>
                <span>{{ recommendationText(row) }}</span>
                <span :class="{ 'is-ready': row.on_disk }">{{ statusText(row) }}</span>
              </span>
              <p>{{ row.use_for }}</p>
            </div>
            <div class="row-actions">
              <NButton v-if="!row.active" size="small" :loading="usingKey === row.key" @click="useModel(row)">
                Use
              </NButton>
              <NButton
                size="small"
                :loading="downloadingKey === row.key"
                @click="downloadOne(row.key, row.on_disk)"
              >
                {{ row.on_disk ? "Re-download" : "Download" }}
              </NButton>
              <NButton v-if="isCustom(row)" size="small" quaternary @click="openEditModel(row)">Edit</NButton>
              <NButton v-if="isCustom(row)" size="small" quaternary @click="confirmDeleteModel(row)">
                Delete
              </NButton>
              <NPopconfirm v-if="row.on_disk" @positive-click="deleteOne(row.key)">
                <template #trigger>
                  <NButton size="small" quaternary :loading="deletingKey === row.key">Remove</NButton>
                </template>
                Remove {{ modelTitle(row) }} from this server?
              </NPopconfirm>
            </div>
          </article>
        </div>
        <div class="or-table-wrap or-table-desktop">
          <NDataTable
            :columns="columns"
            :data="filteredRows"
            :bordered="false"
            size="medium"
            :row-key="(row: ModelCatalogEntry) => row.key"
          />
        </div>
        <p class="table-total">
          {{ filteredRows.length }}
          <template v-if="filteredRows.length !== status.catalog.length">
            of {{ status.catalog.length }}
          </template>
          model{{ filteredRows.length === 1 ? "" : "s" }}
        </p>
      </template>

      <NCollapse v-model:expanded-names="advancedOpen">
        <NCollapseItem title="Advanced" name="advanced">
          <h3 class="subhead">How matching runs</h3>
          <p class="hint">
            Automatic uses a downloaded file when you have one, and a simple built-in guess when you do not.
            ONNX is the file format of those downloads. You do not install it separately.
          </p>
          <div class="inference-controls">
            <NSelect v-model:value="inferenceDraft" :options="inferenceOptions" />
            <NButton :loading="savingInference" :disabled="!inferenceDirty" @click="saveInference">
              Save
            </NButton>
          </div>
          <p v-if="effectiveRuntime" class="hint runtime-line">
            Right now: {{ effectiveRuntime.summary }}.
            <template v-if="status.inference_backend === 'auto'">
              {{ effectiveRuntime.onnxCount }} of
              {{ effectiveRuntime.onnxCount + effectiveRuntime.heuristicCount }}
              jobs use a downloaded file.
            </template>
          </p>
          <NAlert
            v-if="effectiveRuntime?.warnings?.length"
            type="warning"
            :bordered="false"
            class="warn-alert"
          >
            <ul class="warn-list">
              <li v-for="(w, i) in effectiveRuntime.warnings" :key="i">{{ w }}</li>
            </ul>
          </NAlert>

          <h3 class="subhead">Where these files are stored</h3>
          <p class="hint">
            Downloads are stored in this folder. How each file runs is saved with that model. Recommended sets are saved in the database, so a new set can be added without changing this page.
          </p>
          <p class="cell-meta">{{ status.pack_dir }}</p>
          <div v-if="Object.keys(status.loaded_models).length" class="tag-row">
            <NTag
              v-for="key in Object.keys(status.loaded_models)"
              :key="key"
              size="small"
              round
              :bordered="false"
            >
              {{ catalogByKey.get(key)?.label || key }}
            </NTag>
          </div>
        </NCollapseItem>
      </NCollapse>

      <NModal
        v-model:show="showModelForm"
        preset="card"
        :title="editingKey ? 'Edit model' : 'Add a model'"
        class="or-modal"
      >
        <NForm label-placement="top">
          <NFormItem label="Name" required>
            <NInput v-model:value="formLabel" placeholder="Community voice model" />
          </NFormItem>
          <NFormItem label="Category" required>
            <NSelect
              :value="formCategory"
              :options="groupOptions"
              :disabled="editingKey != null"
              @update:value="onFormCategory"
            />
          </NFormItem>
          <p class="hint">
            Your file should work like the other models in this category. Saved samples keep the version below. Change the version when you replace the file, then re-download.
          </p>
          <NFormItem label="Version" required>
            <NInput v-model:value="formVersion" placeholder="my-voice-v1" />
          </NFormItem>
          <NFormItem label="Download link" required>
            <NInput v-model:value="formUrl" placeholder="https://example.com/model.onnx" />
          </NFormItem>
          <template v-if="settingEntries().length">
            <h3 class="subhead">Recommended settings</h3>
            <p class="hint">These match this category. Change a number only when your file needs a different size.</p>
            <NFormItem v-for="field in settingEntries()" :key="field.key" :label="field.label">
              <NInputNumber
                v-if="field.numeric"
                :value="Number(formOnnx[field.key])"
                class="setting-input"
                @update:value="(value) => (formOnnx[field.key] = value ?? 0)"
              />
              <NInput v-else v-model:value="formOnnx[field.key] as string" />
            </NFormItem>
          </template>
        </NForm>
        <template #footer>
          <div class="or-modal-footer">
            <NButton @click="showModelForm = false">Cancel</NButton>
            <NButton
              type="primary"
              :loading="savingModel"
              :disabled="!formLabel.trim() || !formVersion.trim() || !formUrl.trim()"
              @click="saveModel"
            >
              {{ editingKey ? "Save" : "Add" }}
            </NButton>
          </div>
        </template>
      </NModal>
    </template>
  </div>
</template>

<style scoped>
.models-page {
  display: flex;
  flex-direction: column;
  gap: var(--or-section-gap);
}

.models-page :deep(.app-page-header) {
  margin-bottom: 0;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--or-inline-gap);
}

.search-control {
  width: 240px;
  max-width: 100%;
}

.filter-control {
  width: 200px;
  max-width: 100%;
}

.hint,
.cell-meta,
.table-total,
.filter-empty {
  margin: 0;
  color: var(--n-text-color-3);
  font-size: 0.875rem;
  line-height: 1.45;
}

.filter-empty {
  text-align: center;
}

.table-total {
  font-size: 0.8125rem;
}

.model-card {
  cursor: default;
}

.model-card:hover {
  border-color: var(--or-line, var(--n-border-color));
}

.model-card-copy p {
  margin: 4px 0 0;
  color: var(--n-text-color-3);
  font-size: 0.875rem;
}

.models-page :deep(.name-cell) {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}

.models-page :deep(.name-line) {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.models-page :deep(.cell-meta) {
  color: var(--n-text-color-3);
  font-size: 0.8125rem;
}

.models-page :deep(.cell-warn) {
  color: var(--n-warning-color);
  font-size: 0.8125rem;
}

.models-page :deep(.is-ready),
.is-ready {
  color: var(--n-success-color);
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.guess-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
}

.subhead {
  margin: 16px 0 0;
  font-size: 0.9375rem;
  font-weight: 600;
}

.subhead:first-child {
  margin-top: 0;
}

.inference-controls {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 12px;
  max-width: 28rem;
}

.inference-controls :deep(.n-select) {
  flex: 1;
  min-width: 0;
}

.setting-input {
  width: 100%;
}

.runtime-line {
  margin-top: 10px;
}

.warn-alert {
  margin-top: 12px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.warn-list {
  margin: 0;
  padding-left: 1.1rem;
}

@media (max-width: 720px) {
  .search-control,
  .filter-control,
  .inference-controls {
    width: 100%;
  }

  .inference-controls {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
